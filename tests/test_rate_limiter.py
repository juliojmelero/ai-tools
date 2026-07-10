from __future__ import annotations

from threading import Event, Lock
from time import monotonic
from uuid import uuid4

import pytest

from research_engine.rate_limiter import (
    RateLimitPolicy,
    RateLimiterRegistry,
    TokenBucketRateLimiter,
    get_rate_limiter_registry,
)
from research_engine.search_engine import SearchEngine
from research_engine.search_executor import SearchExecutor
from research_engine.search_models import (
    ExecutionPolicy,
    ProviderDeadline,
    ProviderRequest,
    ProviderStatus,
    RetryPolicy,
)
from tests.test_search_engine import FakeProviderManager, FakeRegistry


class FakeClock:
    def __init__(self, now: float = 0.0):
        self.now = now
        self.sleeps: list[float] = []
        self._lock = Lock()

    def __call__(self) -> float:
        with self._lock:
            return self.now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.sleeps.append(seconds)
            self.now += seconds


class FunctionProvider:
    def __init__(self, search):
        self.search = search


def deadline(expires_at: float = 100.0) -> ProviderDeadline:
    return ProviderDeadline(
        timeout_seconds=expires_at,
        expires_at=expires_at,
    )


def request(provider_id: str, provider, ordinal: int = 0) -> ProviderRequest:
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


def test_rate_limit_policy_validation():
    for value in (True, 0, -1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            RateLimitPolicy(value, 1)
    for value in (True, 1.5, "1"):
        with pytest.raises(TypeError):
            RateLimitPolicy(1, value)
    with pytest.raises(ValueError):
        RateLimitPolicy(1, 0)


def test_first_request_consumes_available_token_and_next_waits_for_refill():
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(
        RateLimitPolicy(2, 1), clock=clock, sleeper=clock.sleep
    )
    terminal = Event()

    assert limiter.acquire(deadline(), terminal)
    assert clock.sleeps == []
    assert limiter.acquire(deadline(), terminal)
    assert sum(clock.sleeps) == pytest.approx(0.5)


def test_burst_capacity_permits_exact_configured_burst():
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(
        RateLimitPolicy(10, 3), clock=clock, sleeper=clock.sleep
    )
    terminal = Event()

    assert all(limiter.acquire(deadline(), terminal) for _ in range(3))
    assert clock.sleeps == []
    assert limiter.acquire(deadline(), terminal)
    assert sum(clock.sleeps) == pytest.approx(0.1)


def test_lazy_refill_is_exact_and_never_exceeds_capacity():
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(
        RateLimitPolicy(4, 2), clock=clock, sleeper=clock.sleep
    )
    terminal = Event()

    assert limiter.acquire(deadline(), terminal)
    assert limiter.acquire(deadline(), terminal)
    clock.now += 0.25
    assert limiter.acquire(deadline(), terminal)
    assert clock.sleeps == []
    clock.now += 100
    assert limiter.acquire(deadline(200), terminal)
    assert limiter.acquire(deadline(200), terminal)
    assert limiter.acquire(deadline(200), terminal)
    assert sum(clock.sleeps) == pytest.approx(0.25)


def test_each_sequential_attempt_reacquires_a_token():
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(
        RateLimitPolicy(5, 1), clock=clock, sleeper=clock.sleep
    )
    terminal = Event()

    assert limiter.acquire(deadline(), terminal)  # initial attempt
    assert limiter.acquire(deadline(), terminal)  # retry attempt
    assert sum(clock.sleeps) == pytest.approx(0.2)


def test_separate_providers_have_independent_buckets():
    clock = FakeClock()
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    policy = RateLimitPolicy(1, 1)
    terminal = Event()

    first = registry.get("first", policy)
    second = registry.get("second", policy)
    assert first is not second
    assert first.acquire(deadline(), terminal)
    assert second.acquire(deadline(), terminal)
    assert clock.sleeps == []


def test_separate_executors_share_process_registry_limiter():
    provider_id = f"shared-{uuid4()}"
    policy = RateLimitPolicy(10, 1)
    execution_policy = ExecutionPolicy(default_rate_limit_policy=policy)
    first = SearchExecutor(execution_policy)
    second = SearchExecutor(execution_policy)

    assert first._rate_limiter_registry is second._rate_limiter_registry
    registry = get_rate_limiter_registry()
    assert registry.get(provider_id, policy) is registry.get(provider_id, policy)


def test_deadline_expiring_while_waiting_returns_false():
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(
        RateLimitPolicy(1, 1), clock=clock, sleeper=clock.sleep
    )
    terminal = Event()

    assert limiter.acquire(deadline(), terminal)
    assert not limiter.acquire(deadline(0.2), terminal)
    assert sum(clock.sleeps) == pytest.approx(0.2)


def test_terminal_execution_state_interrupts_bounded_waiting():
    clock = FakeClock()
    terminal = Event()

    def interrupting_sleep(seconds: float) -> None:
        clock.sleep(seconds)
        terminal.set()

    limiter = TokenBucketRateLimiter(
        RateLimitPolicy(1, 1),
        clock=clock,
        sleeper=interrupting_sleep,
        max_sleep_seconds=0.05,
    )
    assert limiter.acquire(deadline(), terminal)

    assert not limiter.acquire(deadline(), terminal)
    assert clock.sleeps == [0.05]


def test_one_provider_search_uses_limiter():
    start = monotonic()
    clock = FakeClock(start)
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    policy = RateLimitPolicy(2, 1)
    provider = FunctionProvider(lambda **kwargs: {"results": []})
    limiter = registry.get("one", policy)
    assert limiter.acquire(deadline(start + 10), Event())
    executor = SearchExecutor(
        ExecutionPolicy(default_rate_limit_policy=policy),
        rate_limiter_registry=registry,
    )

    outcome = executor.execute((request("one", provider),))[0]

    assert outcome.status is ProviderStatus.SUCCESS
    assert sum(clock.sleeps) == pytest.approx(0.5)


def test_transient_failure_then_success_consumes_two_tokens():
    clock = FakeClock()
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    policy = RateLimitPolicy(5, 1)
    responses = iter((ConnectionError("temporary"), {"results": []}))
    calls = 0

    def search(**kwargs):
        nonlocal calls
        calls += 1
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    executor = SearchExecutor(
        ExecutionPolicy(
            default_provider_timeout=1,
            retry_policy=RetryPolicy(initial_backoff=0),
            default_rate_limit_policy=policy,
        ),
        clock=clock,
        sleeper=clock.sleep,
        rate_limiter_registry=registry,
    )

    outcome = executor.execute((request("retrying", FunctionProvider(search)),))[0]

    assert outcome.status is ProviderStatus.SUCCESS
    assert calls == 2
    assert outcome.attempt_count == 2
    assert sum(clock.sleeps) == pytest.approx(0.2)


def test_retry_can_time_out_waiting_for_token_without_second_provider_call():
    clock = FakeClock()
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    calls = 0

    def transient(**kwargs):
        nonlocal calls
        calls += 1
        raise ConnectionError("temporary")

    executor = SearchExecutor(
        ExecutionPolicy(
            default_provider_timeout=0.1,
            retry_policy=RetryPolicy(initial_backoff=0),
            default_rate_limit_policy=RateLimitPolicy(1, 1),
        ),
        clock=clock,
        sleeper=clock.sleep,
        rate_limiter_registry=registry,
    )

    outcome = executor.execute((request("retrying", FunctionProvider(transient)),))[0]

    assert calls == 1
    assert outcome.status is ProviderStatus.TIMED_OUT
    assert [attempt.status for attempt in outcome.attempts] == [
        ProviderStatus.FAILED,
        ProviderStatus.TIMED_OUT,
    ]


def test_multi_provider_search_remains_deterministic_with_rate_limits():
    policy = RateLimitPolicy(100, 10)
    providers = {
        "first": FunctionProvider(lambda **kwargs: {"results": [
            {"provider": "first", "doi": "shared", "title": "Shared"}
        ]}),
        "second": FunctionProvider(lambda **kwargs: {"results": [
            {"provider": "second", "doi": "shared", "citations": 7}
        ]}),
    }
    manager = FakeProviderManager([
        {"id": provider_id, "enabled": True} for provider_id in providers
    ])
    engine = SearchEngine(
        provider_manager=manager,
        provider_registry=FakeRegistry(providers),
        executor=SearchExecutor(ExecutionPolicy(
            max_workers=2,
            provider_rate_limit_policies={key: policy for key in providers},
        )),
    )

    result = engine.search("topic", providers=["first", "second"], sort_mode="none")

    assert tuple(outcome.provider_id for outcome in result.provider_outcomes) == (
        "first", "second"
    )
    assert result.publications[0]["_providers"] == ["first", "second"]


def test_successful_provider_is_unaffected_by_another_throttled_provider():
    start = monotonic()
    clock = FakeClock(start)
    registry = RateLimiterRegistry(clock=clock, sleeper=clock.sleep)
    slow_policy = RateLimitPolicy(1, 1)
    registry.get("throttled", slow_policy).acquire(deadline(start + 10), Event())
    providers = {
        "throttled": FunctionProvider(lambda **kwargs: {"results": []}),
        "fast": FunctionProvider(lambda **kwargs: {"results": [
            {"doi": "kept", "title": "Kept"}
        ]}),
    }
    executor = SearchExecutor(
        ExecutionPolicy(
            default_provider_timeout=0.1,
            provider_rate_limit_policies={"throttled": slow_policy},
            max_workers=2,
        ),
        rate_limiter_registry=registry,
    )

    outcomes = executor.execute(tuple(
        request(provider_id, provider, ordinal)
        for ordinal, (provider_id, provider) in enumerate(providers.items())
    ))

    assert outcomes[0].status is ProviderStatus.TIMED_OUT
    assert outcomes[1].status is ProviderStatus.SUCCESS
    assert outcomes[1].records[0]["title"] == "Kept"
