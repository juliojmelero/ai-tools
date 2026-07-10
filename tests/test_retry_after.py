from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from threading import Event, Lock

import pytest

from research_engine.error_classifier import ErrorClassifier
from research_engine.rate_limiter import RateLimitPolicy, RateLimiterRegistry
from research_engine.search_executor import SearchExecutor
from research_engine.search_models import (
    ExecutionPolicy,
    ProviderDeadline,
    ProviderRequest,
    ProviderStatus,
    RetryPolicy,
)


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now
        self.sleeps: list[float] = []
        self.lock = Lock()

    def __call__(self) -> float:
        with self.lock:
            return self.now

    def sleep(self, seconds: float) -> None:
        with self.lock:
            self.sleeps.append(seconds)
            self.now += seconds


class HttpError(Exception):
    def __init__(
        self,
        status_code: int,
        *,
        retry_after: object | None = None,
        response_headers: dict[str, object] | None = None,
        headers: dict[str, object] | None = None,
    ) -> None:
        self.status_code = status_code
        if retry_after is not None:
            self.retry_after = retry_after
        if response_headers is not None:
            self.response = type("Response", (), {"headers": response_headers})()
        if headers is not None:
            self.headers = headers
        super().__init__(f"HTTP {status_code}")


class FunctionProvider:
    def __init__(self, search) -> None:
        self.search = search


def request(provider, provider_id: str = "provider", ordinal: int = 0):
    return ProviderRequest(
        provider_id=provider_id,
        original_query="topic",
        planned_query="topic",
        max_results=20,
        from_year=None,
        until_year=None,
        ordinal=ordinal,
        provider=provider,
    )


def sequence_provider(*values):
    values = iter(values)

    def search(**kwargs):
        value = next(values)
        if isinstance(value, Exception):
            raise value
        return value

    return FunctionProvider(search)


def executor(
    clock: FakeClock,
    *,
    retry: RetryPolicy | None = None,
    timeout: float = 30,
    registry: RateLimiterRegistry | None = None,
    classifier: ErrorClassifier | None = None,
    rate_limit: RateLimitPolicy | None = None,
):
    registry = registry or RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    return SearchExecutor(
        ExecutionPolicy(
            default_provider_timeout=timeout,
            retry_policy=retry or RetryPolicy(),
            default_rate_limit_policy=rate_limit,
        ),
        clock=clock,
        sleeper=clock.sleep,
        error_classifier=classifier,
        rate_limiter_registry=registry,
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (HttpError(429, retry_after=3), 3.0),
        (HttpError(429, retry_after=1.25), 1.25),
        (HttpError(429, response_headers={"Retry-After": "2.5"}), 2.5),
        (HttpError(429, headers={"Retry-After": "4"}), 4.0),
    ],
)
def test_retry_after_numeric_extraction(error, expected):
    decision = ErrorClassifier().classify(error, RetryPolicy())
    assert decision.retry_after_seconds == expected


def test_retry_after_extraction_order_prefers_exception_attribute():
    error = HttpError(
        429,
        retry_after=1,
        response_headers={"Retry-After": "2"},
        headers={"Retry-After": "3"},
    )
    assert ErrorClassifier().classify(error, RetryPolicy()).retry_after_seconds == 1


def test_retry_after_http_date_and_past_date():
    wall_now = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    classifier = ErrorClassifier(wall_clock=lambda: wall_now)
    future = format_datetime(datetime(2025, 1, 1, 0, 0, 7, tzinfo=timezone.utc))
    past = format_datetime(datetime(2024, 12, 31, 23, 59, 0, tzinfo=timezone.utc))

    assert classifier.classify(
        HttpError(429, retry_after=future), RetryPolicy()
    ).retry_after_seconds == 7
    assert classifier.classify(
        HttpError(429, retry_after=past), RetryPolicy()
    ).retry_after_seconds == 0


@pytest.mark.parametrize(
    "value",
    ["not a delay", -1, "-1", float("nan"), "NaN", float("inf"), "inf", True],
)
def test_invalid_retry_after_values_are_ignored(value):
    decision = ErrorClassifier().classify(
        HttpError(429, retry_after=value), RetryPolicy()
    )
    assert decision.retry_after_seconds is None


def test_malformed_retry_after_falls_back_to_exponential_backoff():
    clock = FakeClock()
    outcome = executor(
        clock, retry=RetryPolicy(max_attempts=2, initial_backoff=0.75)
    ).execute((request(sequence_provider(
        HttpError(429, retry_after="bad"), {"results": []}
    )),))[0]

    assert outcome.status is ProviderStatus.SUCCESS
    assert outcome.attempts[0].scheduled_backoff == 0.75
    assert sum(clock.sleeps) == pytest.approx(0.75)


@pytest.mark.parametrize("status", [429, 503])
def test_retry_after_http_failure_then_success(status):
    clock = FakeClock()
    outcome = executor(
        clock, retry=RetryPolicy(max_attempts=2, initial_backoff=0.25)
    ).execute((request(sequence_provider(
        HttpError(status, retry_after=1.5), {"results": []}
    )),))[0]

    assert outcome.status is ProviderStatus.SUCCESS
    assert outcome.attempts[0].scheduled_backoff == 1.5
    assert sum(clock.sleeps) == pytest.approx(1.5)


def test_effective_delay_is_maximum_of_backoff_and_retry_after():
    clock = FakeClock()
    outcome = executor(
        clock, retry=RetryPolicy(max_attempts=2, initial_backoff=2)
    ).execute((request(sequence_provider(
        HttpError(429, retry_after=0.5), {"results": []}
    )),))[0]
    assert outcome.attempts[0].scheduled_backoff == 2
    assert sum(clock.sleeps) == pytest.approx(2)


def test_retry_after_that_cannot_fit_produces_one_final_timeout_attempt():
    clock = FakeClock()
    outcome = executor(
        clock,
        timeout=1,
        retry=RetryPolicy(max_attempts=2, initial_backoff=0.1),
    ).execute((request(sequence_provider(HttpError(429, retry_after=2))),))[0]

    assert outcome.status is ProviderStatus.TIMED_OUT
    assert [attempt.status for attempt in outcome.attempts] == [
        ProviderStatus.FAILED,
        ProviderStatus.TIMED_OUT,
    ]
    assert outcome.attempts[0].scheduled_backoff == 2


def test_cooldown_from_one_executor_delays_another_for_same_provider():
    clock = FakeClock()
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    first = executor(
        clock,
        retry=RetryPolicy(max_attempts=1),
        registry=registry,
    )
    second = executor(clock, registry=registry)

    first.execute((request(
        sequence_provider(HttpError(429, retry_after=3)), "shared"
    ),))
    before = clock.now
    outcome = second.execute((request(
        sequence_provider({"results": []}), "shared"
    ),))[0]

    assert outcome.status is ProviderStatus.SUCCESS
    assert clock.now - before == pytest.approx(3)


def test_shorter_cooldown_does_not_reduce_longer_cooldown():
    clock = FakeClock()
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    registry.apply_cooldown("same", 5)
    clock.now = 1
    registry.apply_cooldown("same", 1)

    assert registry.wait_for_cooldown(
        "same", ProviderDeadline(10, 10), Event()
    )
    assert clock.now == pytest.approx(5)


def test_different_provider_cooldowns_are_independent():
    clock = FakeClock()
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    registry.apply_cooldown("slow", 5)

    assert registry.wait_for_cooldown(
        "fast", ProviderDeadline(1, 1), Event()
    )
    assert clock.now == 0


def test_retry_reacquires_token_after_cooldown():
    clock = FakeClock()
    outcome = executor(
        clock,
        retry=RetryPolicy(max_attempts=2, initial_backoff=0),
        rate_limit=RateLimitPolicy(1, 1),
    ).execute((request(sequence_provider(
        HttpError(429, retry_after=0.1), {"results": []}
    )),))[0]

    assert outcome.status is ProviderStatus.SUCCESS
    assert outcome.attempt_count == 2
    assert sum(clock.sleeps) == pytest.approx(1.0)


def test_retry_after_preserves_deterministic_outcome_ordering():
    clock = FakeClock()
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    outcomes = executor(clock, registry=registry).execute((
        request(sequence_provider(
            HttpError(429, retry_after=0.2), {"results": []}
        ), "retry", 0),
        request(sequence_provider({"results": []}), "success", 1),
    ))
    assert [outcome.provider_id for outcome in outcomes] == ["retry", "success"]
