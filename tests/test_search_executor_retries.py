from __future__ import annotations

from threading import Event, Lock
from time import sleep

import pytest

from research_engine.search_executor import SearchExecutor
from research_engine.search_models import (
    ExecutionPolicy,
    ProviderRequest,
    ProviderStatus,
    RetryPolicy,
)


class FunctionProvider:
    def __init__(self, search):
        self.search = search


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []
        self.lock = Lock()

    def __call__(self):
        with self.lock:
            return self.now

    def sleep(self, delay):
        with self.lock:
            self.sleeps.append(delay)
            self.now += delay


class HttpError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


def request(provider, provider_id="provider", ordinal=0):
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


def executor(*, retry=None, timeout=30, clock=None, jitter_strategy=None, workers=1):
    clock = clock or FakeClock()
    return SearchExecutor(
        ExecutionPolicy(
            default_provider_timeout=timeout,
            max_workers=workers,
            retry_policy=retry or RetryPolicy(),
        ),
        clock=clock,
        sleeper=clock.sleep,
        jitter_strategy=jitter_strategy,
    )


def sequence_provider(*values):
    values = iter(values)

    def search(**kwargs):
        value = next(values)
        if isinstance(value, Exception):
            raise value
        return value

    return FunctionProvider(search)


@pytest.mark.parametrize("failures", [1, 2])
def test_transient_failures_then_success_preserve_attempt_history(failures):
    provider = sequence_provider(
        *([ConnectionError("temporary")] * failures),
        {"results": []},
    )

    outcome = executor().execute((request(provider),))[0]

    assert outcome.status is ProviderStatus.SUCCESS
    assert outcome.attempt_count == failures + 1
    assert len(outcome.attempt_history) == failures + 1
    assert [attempt.attempt_number for attempt in outcome.attempts] == list(
        range(1, failures + 2)
    )
    assert outcome.attempts[-1].status is ProviderStatus.SUCCESS


def test_retryable_failure_exhausts_max_attempts():
    outcome = executor(retry=RetryPolicy(max_attempts=2)).execute((
        request(sequence_provider(ConnectionError("one"), ConnectionError("two"))),
    ))[0]

    assert outcome.status is ProviderStatus.FAILED
    assert outcome.attempt_count == 2
    assert outcome.final_error.retryable is True


@pytest.mark.parametrize("error", [ValueError("bad query"), HttpError(400)])
def test_non_retryable_failure_runs_once(error):
    calls = 0

    def fail(**kwargs):
        nonlocal calls
        calls += 1
        raise error

    outcome = executor().execute((request(FunctionProvider(fail)),))[0]

    assert calls == 1
    assert outcome.attempt_count == 1
    assert outcome.final_error.retryable is False


def test_exact_backoff_sequence_and_cap():
    clock = FakeClock()
    policy = RetryPolicy(
        max_attempts=5,
        initial_backoff=1,
        backoff_multiplier=3,
        max_backoff=5,
    )
    provider = sequence_provider(
        ConnectionError(), ConnectionError(), ConnectionError(), ConnectionError(),
        {"results": []},
    )

    outcome = executor(retry=policy, clock=clock).execute((request(provider),))[0]

    assert sum(clock.sleeps) == pytest.approx(14)
    assert max(clock.sleeps) <= .05
    assert [attempt.scheduled_backoff for attempt in outcome.attempts] == [1, 3, 5, 5, None]


def test_deterministic_jitter_is_injectable():
    clock = FakeClock()
    calls = []

    def jitter(delay, amount, attempt):
        calls.append((delay, amount, attempt))
        return delay + amount

    policy = RetryPolicy(max_attempts=2, initial_backoff=1, max_backoff=3, jitter=.25)
    provider = sequence_provider(ConnectionError(), {"results": []})

    executor(retry=policy, clock=clock, jitter_strategy=jitter).execute((request(provider),))

    assert calls == [(1, .25, 1)]
    assert sum(clock.sleeps) == pytest.approx(1.25)
    assert max(clock.sleeps) <= .05


def test_deadline_prevents_retry_when_backoff_cannot_fit():
    clock = FakeClock()
    provider = sequence_provider(ConnectionError(), {"results": []})

    outcome = executor(
        retry=RetryPolicy(initial_backoff=2), timeout=1, clock=clock
    ).execute((request(provider),))[0]

    assert outcome.status is ProviderStatus.TIMED_OUT
    assert outcome.attempt_count == 2
    assert [attempt.status for attempt in outcome.attempts] == [
        ProviderStatus.FAILED, ProviderStatus.TIMED_OUT,
    ]
    assert clock.sleeps == []


def test_deadline_expiring_during_backoff_returns_timed_out():
    clock = FakeClock()

    def oversleep(delay):
        clock.sleeps.append(delay)
        clock.now += delay + 2

    provider = sequence_provider(ConnectionError(), {"results": []})
    policy = ExecutionPolicy(
        default_provider_timeout=1.5,
        max_workers=1,
        retry_policy=RetryPolicy(initial_backoff=1),
    )
    outcome = SearchExecutor(policy, clock=clock, sleeper=oversleep).execute((request(provider),))[0]

    assert outcome.status is ProviderStatus.TIMED_OUT
    assert outcome.attempt_count == 2


def test_provider_returning_after_deadline_is_timed_out_not_successful():
    clock = FakeClock()

    def late(**kwargs):
        clock.now = 1.01
        return {"results": []}

    outcome = executor(timeout=1, clock=clock).execute((
        request(FunctionProvider(late)),
    ))[0]

    assert outcome.status is ProviderStatus.TIMED_OUT
    assert [attempt.status for attempt in outcome.attempts] == [ProviderStatus.TIMED_OUT]


def test_provider_returning_just_before_deadline_succeeds():
    clock = FakeClock()

    def on_time(**kwargs):
        clock.now = .999
        return {"results": []}

    outcome = executor(timeout=1, clock=clock).execute((
        request(FunctionProvider(on_time)),
    ))[0]

    assert outcome.status is ProviderStatus.SUCCESS


def test_coordinator_timeout_stops_retry_and_preserves_prior_failure():
    calls = 0
    first_failed = Event()

    def transient(**kwargs):
        nonlocal calls
        calls += 1
        first_failed.set()
        raise ConnectionError("temporary")

    policy = ExecutionPolicy(
        default_provider_timeout=.02,
        max_workers=1,
        retry_policy=RetryPolicy(initial_backoff=.1, minimum_attempt_budget=.001),
    )
    outcome = SearchExecutor(policy).execute((request(FunctionProvider(transient)),))[0]
    assert first_failed.is_set()
    sleep(.07)

    assert calls == 1
    assert outcome.status is ProviderStatus.TIMED_OUT
    assert [attempt.status for attempt in outcome.attempts] == [
        ProviderStatus.FAILED, ProviderStatus.TIMED_OUT,
    ]
    assert sum(
        attempt.status is ProviderStatus.TIMED_OUT for attempt in outcome.attempts
    ) == 1


def test_minimum_attempt_budget_prevents_late_retry():
    clock = FakeClock()
    calls = 0

    def transient(**kwargs):
        nonlocal calls
        calls += 1
        clock.now = .95
        raise ConnectionError("temporary")

    policy = RetryPolicy(
        initial_backoff=.01,
        minimum_attempt_budget=.05,
    )
    outcome = executor(retry=policy, timeout=1, clock=clock).execute((
        request(FunctionProvider(transient)),
    ))[0]

    assert calls == 1
    assert outcome.status is ProviderStatus.TIMED_OUT
    assert outcome.attempts[-1].status is ProviderStatus.TIMED_OUT


def test_every_timeout_has_exactly_one_final_timed_out_attempt():
    clock = FakeClock()
    cases = (
        sequence_provider(ConnectionError(), {"results": []}),
        FunctionProvider(lambda **kwargs: (setattr(clock, "now", 2), {"results": []})[1]),
    )

    for provider in cases:
        clock.now = 0
        outcome = executor(
            retry=RetryPolicy(initial_backoff=2), timeout=1, clock=clock
        ).execute((request(provider),))[0]
        assert outcome.attempts[-1].status is ProviderStatus.TIMED_OUT
        assert sum(
            attempt.status is ProviderStatus.TIMED_OUT for attempt in outcome.attempts
        ) == 1


def test_retrying_provider_does_not_affect_success_or_outcome_order():
    clock = FakeClock()
    requests = (
        request(sequence_provider(ConnectionError(), {"results": []}), "retry", 0),
        request(sequence_provider({"results": []}), "success", 1),
    )

    outcomes = executor(clock=clock, workers=2).execute(requests)

    assert [outcome.provider_id for outcome in outcomes] == ["retry", "success"]
    assert [outcome.status for outcome in outcomes] == [
        ProviderStatus.SUCCESS, ProviderStatus.SUCCESS,
    ]
    assert [outcome.attempt_count for outcome in outcomes] == [2, 1]


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_http_statuses_are_retried(status):
    provider = sequence_provider(HttpError(status), {"results": []})
    assert executor().execute((request(provider),))[0].attempt_count == 2
