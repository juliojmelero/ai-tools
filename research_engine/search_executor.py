from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace
from threading import Lock
from time import monotonic, sleep
from typing import Any, Callable

from research_engine.error_classifier import ErrorClassifier
from research_engine.rate_limiter import (
    RateLimiterRegistry,
    get_rate_limiter_registry,
)
from research_engine.search_models import (
    ExecutionPolicy,
    ProviderDeadline,
    ProviderExecutionError,
    ProviderAttempt,
    ProviderOutcome,
    ProviderRequest,
    ProviderStatus,
)


class InvalidProviderResponse(ValueError):
    pass


class _ProviderExecutionState:
    """Thread-safe terminal state and immutable attempt snapshots for one request."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._terminal_status: ProviderStatus | None = None
        self._attempts: tuple[ProviderAttempt, ...] = ()
        self._active_attempt: tuple[int, float] | None = None

    def begin_attempt(
        self,
        attempt_number: int,
        now: float,
        expires_at: float,
        minimum_budget: float,
    ) -> bool:
        with self._lock:
            if self._terminal_status is not None:
                return False
            if expires_at - now <= minimum_budget:
                return False
            self._active_attempt = (attempt_number, now)
            return True

    def complete_success(
        self,
        now: float,
        expires_at: float,
        timeout_error: ProviderExecutionError,
    ) -> ProviderStatus:
        with self._lock:
            if self._terminal_status is not None:
                return self._terminal_status
            if now >= expires_at:
                self._append_timeout_locked(now, timeout_error)
                return ProviderStatus.TIMED_OUT
            attempt_number, started = self._active_attempt
            self._attempts += (ProviderAttempt(
                attempt_number=attempt_number,
                started_at=started,
                elapsed_ms=max(0, round((now - started) * 1000)),
                status=ProviderStatus.SUCCESS,
            ),)
            self._active_attempt = None
            self._terminal_status = ProviderStatus.SUCCESS
            return ProviderStatus.SUCCESS

    def complete_failure(
        self,
        now: float,
        error: ProviderExecutionError,
        scheduled_backoff: float | None,
        terminal: bool,
    ) -> bool:
        with self._lock:
            if self._terminal_status is not None:
                return False
            attempt_number, started = self._active_attempt
            self._attempts += (ProviderAttempt(
                attempt_number=attempt_number,
                started_at=started,
                elapsed_ms=max(0, round((now - started) * 1000)),
                status=ProviderStatus.FAILED,
                error=error,
                scheduled_backoff=scheduled_backoff,
            ),)
            self._active_attempt = None
            if terminal:
                self._terminal_status = ProviderStatus.FAILED
            return True

    def time_out(self, now: float, error: ProviderExecutionError) -> bool:
        with self._lock:
            if self._terminal_status is not None:
                return False
            self._append_timeout_locked(now, error)
            return True

    def _append_timeout_locked(
        self,
        now: float,
        error: ProviderExecutionError,
    ) -> None:
        if self._active_attempt is None:
            attempt_number = self._attempts[-1].attempt_number + 1 if self._attempts else 1
            started = now
        else:
            attempt_number, started = self._active_attempt
        self._attempts += (ProviderAttempt(
            attempt_number=attempt_number,
            started_at=started,
            elapsed_ms=max(0, round((now - started) * 1000)),
            status=ProviderStatus.TIMED_OUT,
            error=error,
        ),)
        self._active_attempt = None
        self._terminal_status = ProviderStatus.TIMED_OUT

    def snapshot(self) -> tuple[ProviderStatus | None, tuple[ProviderAttempt, ...]]:
        with self._lock:
            return self._terminal_status, self._attempts

    def is_set(self) -> bool:
        """Return whether this request has reached a terminal state."""
        with self._lock:
            return self._terminal_status is not None


class SearchExecutor:
    """Bounded concurrent executor with one terminal outcome per request."""

    def __init__(
        self,
        policy: ExecutionPolicy | None = None,
        *,
        max_workers: int | None = None,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
        jitter_strategy: Callable[[float, float, int], float] | None = None,
        error_classifier: ErrorClassifier | None = None,
        rate_limiter_registry: RateLimiterRegistry | None = None,
    ):
        if policy is not None and max_workers is not None:
            raise TypeError("provide either policy or max_workers, not both")
        if policy is not None and not isinstance(policy, ExecutionPolicy):
            raise TypeError("policy must be an ExecutionPolicy")
        self.policy = policy or ExecutionPolicy(
            max_workers=8 if max_workers is None else max_workers
        )
        self._clock = clock
        self._sleep = sleeper
        self._jitter_strategy = jitter_strategy or self._zero_jitter
        self._error_classifier = error_classifier or ErrorClassifier()
        if (
            rate_limiter_registry is not None
            and not isinstance(rate_limiter_registry, RateLimiterRegistry)
        ):
            raise TypeError("rate_limiter_registry must be a RateLimiterRegistry")
        self._rate_limiter_registry = (
            rate_limiter_registry or get_rate_limiter_registry()
        )

    @property
    def max_workers(self) -> int:
        return self.policy.max_workers

    def execute(self, requests: Sequence[ProviderRequest]) -> tuple[ProviderOutcome, ...]:
        requests = tuple(requests)
        if not requests:
            return ()

        started = self._clock()
        overall_expires_at = (
            None
            if self.policy.overall_timeout is None
            else started + self.policy.overall_timeout
        )
        prepared = tuple(
            replace(
                request,
                deadline=self._deadline(started, overall_expires_at),
            )
            for request in requests
        )
        states = {
            request.ordinal: _ProviderExecutionState()
            for request in prepared
        }
        if len(states) != len(prepared):
            raise ValueError("provider request ordinals must be unique")

        effective_workers = min(self.max_workers, len(prepared))
        executor = ThreadPoolExecutor(max_workers=effective_workers)
        future_requests: dict[Future[ProviderOutcome], ProviderRequest] = {
            executor.submit(self._execute_one, request, states[request.ordinal]): request
            for request in prepared
        }
        outcomes: dict[int, ProviderOutcome] = {}
        pending = set(future_requests)
        try:
            while pending:
                nearest_expiry = min(
                    future_requests[future].deadline.expires_at
                    for future in pending
                )
                done, _ = wait(
                    pending,
                    timeout=max(0.0, nearest_expiry - self._clock()),
                    return_when=FIRST_COMPLETED,
                )

                for future in done:
                    request = future_requests[future]
                    outcomes[request.ordinal] = future.result()
                    pending.remove(future)

                now = self._clock()
                expired = sorted(
                    (
                        future
                        for future in pending
                        if future_requests[future].deadline.expires_at <= now
                    ),
                    key=lambda future: future_requests[future].ordinal,
                )
                for future in expired:
                    request = future_requests[future]
                    state = states[request.ordinal]
                    state.time_out(now, self._timeout_error(request))
                    future.cancel()
                    outcomes[request.ordinal] = self._outcome_from_state(
                        request, state, started
                    )
                    pending.remove(future)
        finally:
            # ThreadPoolExecutor cannot forcibly terminate running blocking calls.
            # They may finish in the background, while queued calls are cancelled.
            executor.shutdown(wait=False, cancel_futures=True)

        return tuple(outcomes[request.ordinal] for request in prepared)

    def _deadline(
        self,
        started: float,
        overall_expires_at: float | None,
    ) -> ProviderDeadline:
        provider_expires_at = started + self.policy.default_provider_timeout
        limited_by_overall = (
            overall_expires_at is not None
            and overall_expires_at < provider_expires_at
        )
        expires_at = (
            overall_expires_at if limited_by_overall else provider_expires_at
        )
        return ProviderDeadline(
            timeout_seconds=expires_at - started,
            expires_at=expires_at,
            limited_by_overall_timeout=limited_by_overall,
        )

    def _execute_one(
        self,
        request: ProviderRequest,
        state: _ProviderExecutionState,
    ) -> ProviderOutcome:
        started = self._clock()

        if request.preparation_error is not None:
            return self._failed_outcome(
                request=request,
                error=request.preparation_error,
                attempt_count=0,
                started=started,
            )

        retry_policy = self.policy.retry_policy
        for attempt_number in range(1, retry_policy.max_attempts + 1):
            attempt_started = self._clock()
            if not state.begin_attempt(
                attempt_number,
                attempt_started,
                request.deadline.expires_at,
                retry_policy.minimum_attempt_budget,
            ):
                state.time_out(attempt_started, self._timeout_error(request))
                return self._outcome_from_state(request, state, started)

            provider_policies = self.policy.provider_rate_limit_policies
            rate_limit_policy = provider_policies.get(
                request.provider_id,
                self.policy.default_rate_limit_policy,
            )
            limiter = self._rate_limiter_registry.get(
                request.provider_id,
                rate_limit_policy,
            )
            if not self._rate_limiter_registry.wait_for_cooldown(
                request.provider_id, request.deadline, state
            ):
                state.time_out(self._clock(), self._timeout_error(request))
                return self._outcome_from_state(request, state, started)
            if limiter is not None and not limiter.acquire(request.deadline, state):
                state.time_out(self._clock(), self._timeout_error(request))
                return self._outcome_from_state(request, state, started)

            now = self._clock()
            if state.is_set() or now >= request.deadline.expires_at:
                state.time_out(now, self._timeout_error(request))
                return self._outcome_from_state(request, state, started)
            try:
                response = request.provider.search(
                    query=request.planned_query,
                    max_results=request.max_results,
                    from_year=request.from_year,
                    until_year=request.until_year,
                )
                if self._clock() >= request.deadline.expires_at:
                    state.time_out(self._clock(), self._timeout_error(request))
                    return self._outcome_from_state(request, state, started)
                records = self._validate_response(response, request.provider_id)
            except InvalidProviderResponse as exc:
                if self._clock() >= request.deadline.expires_at:
                    state.time_out(self._clock(), self._timeout_error(request))
                    return self._outcome_from_state(request, state, started)
                error = ProviderExecutionError(
                    code="invalid_provider_response",
                    message=str(exc),
                    error_type=type(exc).__name__,
                )
                state.complete_failure(self._clock(), error, None, terminal=True)
                return self._outcome_from_state(request, state, started)
            except Exception as exc:
                if self._clock() >= request.deadline.expires_at:
                    state.time_out(self._clock(), self._timeout_error(request))
                    return self._outcome_from_state(request, state, started)
                decision = self._error_classifier.classify(exc, retry_policy)
                can_retry = decision.retryable and attempt_number < retry_policy.max_attempts
                backoff = None
                if can_retry:
                    backoff = max(
                        self._backoff(attempt_number),
                        decision.retry_after_seconds or 0.0,
                    )
                if decision.retryable and decision.retry_after_seconds is not None:
                    self._rate_limiter_registry.apply_cooldown(
                        request.provider_id, decision.retry_after_seconds
                    )
                if backoff is not None and not self._retry_fits(request, backoff):
                    state.complete_failure(
                        self._clock(), decision.error, backoff, terminal=False
                    )
                    state.time_out(self._clock(), self._timeout_error(request))
                    return self._outcome_from_state(request, state, started)
                if not state.complete_failure(
                    self._clock(), decision.error, backoff, terminal=not can_retry
                ):
                    return self._outcome_from_state(request, state, started)
                if not can_retry:
                    return self._outcome_from_state(request, state, started)
                if not self._wait_backoff(request, state, backoff):
                    return self._outcome_from_state(request, state, started)
                continue

            status = state.complete_success(
                self._clock(), request.deadline.expires_at, self._timeout_error(request)
            )
            return self._outcome_from_state(
                request,
                state,
                started,
                records=records if status is ProviderStatus.SUCCESS else (),
            )

        raise AssertionError("retry loop terminated without an outcome")

    @staticmethod
    def _validate_response(
        response: Any,
        provider_id: str,
    ) -> tuple[dict[str, Any], ...]:
        if not isinstance(response, Mapping):
            raise InvalidProviderResponse("provider response must be a mapping")
        if "results" not in response:
            raise InvalidProviderResponse("provider response must contain 'results'")

        results = response["results"]
        if not isinstance(results, list):
            raise InvalidProviderResponse("provider response 'results' must be a list")

        normalized = []
        for index, record in enumerate(results):
            if not isinstance(record, Mapping):
                raise InvalidProviderResponse(
                    f"provider response result at index {index} must be a mapping"
                )
            copied = dict(record)
            if not copied.get("provider"):
                copied["provider"] = provider_id
            normalized.append(copied)

        return tuple(normalized)

    def _elapsed_ms(self, started: float) -> int:
        return max(0, round((self._clock() - started) * 1000))

    def _backoff(self, attempt_number: int) -> float:
        policy = self.policy.retry_policy
        base = min(
            policy.max_backoff,
            policy.initial_backoff * policy.backoff_multiplier ** (attempt_number - 1),
        )
        jittered = self._jitter_strategy(base, policy.jitter, attempt_number)
        return max(0.0, min(policy.max_backoff, jittered))

    @staticmethod
    def _zero_jitter(delay: float, jitter: float, attempt_number: int) -> float:
        return delay

    def _retry_fits(self, request: ProviderRequest, backoff: float) -> bool:
        required = backoff + self.policy.retry_policy.minimum_attempt_budget
        return required < request.deadline.expires_at - self._clock()

    def _wait_backoff(
        self,
        request: ProviderRequest,
        state: _ProviderExecutionState,
        backoff: float,
    ) -> bool:
        wait_until = self._clock() + backoff
        while True:
            now = self._clock()
            terminal_status, _ = state.snapshot()
            if terminal_status is not None:
                return False
            if now >= request.deadline.expires_at:
                state.time_out(now, self._timeout_error(request))
                return False
            remaining_backoff = wait_until - now
            if remaining_backoff <= 0:
                return True
            self._sleep(min(
                0.05,
                remaining_backoff,
                request.deadline.expires_at - now,
            ))

    @staticmethod
    def _timeout_error(request: ProviderRequest) -> ProviderExecutionError:
        deadline = request.deadline
        return ProviderExecutionError(
            code="provider_timeout",
            message=(
                f"Provider '{request.provider_id}' exceeded its "
                f"{deadline.timeout_seconds:g} second execution deadline"
            ),
            error_type="ProviderTimeoutError",
        )

    def _outcome_from_state(
        self,
        request: ProviderRequest,
        state: _ProviderExecutionState,
        started: float,
        records: tuple[dict[str, Any], ...] = (),
    ) -> ProviderOutcome:
        status, attempts = state.snapshot()
        if status is None:
            raise RuntimeError("provider execution state is not terminal")
        error = None if status is ProviderStatus.SUCCESS else attempts[-1].error
        return ProviderOutcome(
            provider_id=request.provider_id,
            status=status,
            original_query=request.original_query,
            planned_query=request.planned_query,
            records=records if status is ProviderStatus.SUCCESS else (),
            attempt_count=len(attempts),
            elapsed_ms=self._elapsed_ms(started),
            error=error,
            ordinal=request.ordinal,
            deadline=request.deadline,
            attempts=attempts,
        )

    def _failed_outcome(
        self,
        request: ProviderRequest,
        error: ProviderExecutionError,
        attempt_count: int,
        started: float,
        attempts: tuple[ProviderAttempt, ...] = (),
    ) -> ProviderOutcome:
        return ProviderOutcome(
            provider_id=request.provider_id,
            status=ProviderStatus.FAILED,
            original_query=request.original_query,
            planned_query=request.planned_query,
            records=(),
            attempt_count=attempt_count,
            elapsed_ms=self._elapsed_ms(started),
            error=error,
            ordinal=request.ordinal,
            deadline=request.deadline,
            attempts=attempts,
        )
