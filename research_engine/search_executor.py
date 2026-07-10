from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace
from time import monotonic
from typing import Any

from research_engine.search_models import (
    ExecutionPolicy,
    ProviderDeadline,
    ProviderExecutionError,
    ProviderOutcome,
    ProviderRequest,
    ProviderStatus,
)


class InvalidProviderResponse(ValueError):
    pass


class SearchExecutor:
    """Bounded concurrent executor with one terminal outcome per request."""

    def __init__(
        self,
        policy: ExecutionPolicy | None = None,
        *,
        max_workers: int | None = None,
    ):
        if policy is not None and max_workers is not None:
            raise TypeError("provide either policy or max_workers, not both")
        if policy is not None and not isinstance(policy, ExecutionPolicy):
            raise TypeError("policy must be an ExecutionPolicy")
        self.policy = policy or ExecutionPolicy(
            max_workers=8 if max_workers is None else max_workers
        )

    @property
    def max_workers(self) -> int:
        return self.policy.max_workers

    def execute(self, requests: Sequence[ProviderRequest]) -> tuple[ProviderOutcome, ...]:
        requests = tuple(requests)
        if not requests:
            return ()

        started = monotonic()
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

        effective_workers = min(self.max_workers, len(prepared))
        executor = ThreadPoolExecutor(max_workers=effective_workers)
        future_requests: dict[Future[ProviderOutcome], ProviderRequest] = {
            executor.submit(self._execute_one, request): request
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
                    timeout=max(0.0, nearest_expiry - monotonic()),
                    return_when=FIRST_COMPLETED,
                )

                for future in done:
                    request = future_requests[future]
                    outcomes[request.ordinal] = future.result()
                    pending.remove(future)

                now = monotonic()
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
                    future.cancel()
                    outcomes[request.ordinal] = self._timed_out_outcome(request)
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

    def _execute_one(self, request: ProviderRequest) -> ProviderOutcome:
        started = monotonic()

        if request.preparation_error is not None:
            return self._failed_outcome(
                request=request,
                error=request.preparation_error,
                attempt_count=0,
                started=started,
            )

        try:
            response = request.provider.search(
                query=request.planned_query,
                max_results=request.max_results,
                from_year=request.from_year,
                until_year=request.until_year,
            )
            records = self._validate_response(response, request.provider_id)
        except InvalidProviderResponse as exc:
            return self._failed_outcome(
                request=request,
                error=ProviderExecutionError(
                    code="invalid_provider_response",
                    message=str(exc),
                    error_type=type(exc).__name__,
                ),
                attempt_count=1,
                started=started,
            )
        except Exception as exc:
            return self._failed_outcome(
                request=request,
                error=ProviderExecutionError(
                    code="provider_execution_failed",
                    message=str(exc) or type(exc).__name__,
                    error_type=type(exc).__name__,
                ),
                attempt_count=1,
                started=started,
            )

        return ProviderOutcome(
            provider_id=request.provider_id,
            status=ProviderStatus.SUCCESS,
            original_query=request.original_query,
            planned_query=request.planned_query,
            records=records,
            attempt_count=1,
            elapsed_ms=self._elapsed_ms(started),
            error=None,
            ordinal=request.ordinal,
            deadline=request.deadline,
        )

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

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((monotonic() - started) * 1000))

    def _failed_outcome(
        self,
        request: ProviderRequest,
        error: ProviderExecutionError,
        attempt_count: int,
        started: float,
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
        )

    def _timed_out_outcome(self, request: ProviderRequest) -> ProviderOutcome:
        deadline = request.deadline
        return ProviderOutcome(
            provider_id=request.provider_id,
            status=ProviderStatus.TIMED_OUT,
            original_query=request.original_query,
            planned_query=request.planned_query,
            records=(),
            attempt_count=1,
            elapsed_ms=max(0, round(deadline.timeout_seconds * 1000)),
            error=ProviderExecutionError(
                code="provider_timeout",
                message=(
                    f"Provider '{request.provider_id}' exceeded its "
                    f"{deadline.timeout_seconds:g} second execution deadline"
                ),
                error_type="ProviderTimeoutError",
            ),
            ordinal=request.ordinal,
            deadline=deadline,
        )
