from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from threading import Event
from time import monotonic, sleep

import pytest

from research_engine.search_engine import SearchEngine
from research_engine.search_executor import SearchExecutor
from research_engine.search_models import (
    ExecutionPolicy,
    ProviderRequest,
    ProviderStatus,
    SearchResult,
)
from tests.test_search_engine import FakeProviderManager, FakeRegistry


class FunctionProvider:
    def __init__(self, search):
        self.search = search


def provider_request(provider_id, provider, ordinal=0):
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


def timeout_executor(timeout=0.01, max_workers=8):
    return SearchExecutor(ExecutionPolicy(
        default_provider_timeout=timeout,
        max_workers=max_workers,
    ))


def timeout_engine(providers, timeout=0.01):
    configurations = [
        {"id": provider_id, "enabled": True}
        for provider_id in providers
    ]
    return SearchEngine(
        provider_manager=FakeProviderManager(configurations),
        provider_registry=FakeRegistry(providers),
        executor=timeout_executor(timeout),
    )


def slow_provider(**kwargs):
    sleep(0.05)
    return {"results": [{"doi": "late", "title": "Late"}]}


def test_one_provider_timeout_has_structured_outcome_information():
    outcome = timeout_executor().execute((
        provider_request("slow", FunctionProvider(slow_provider)),
    ))[0]

    assert outcome.status is ProviderStatus.TIMED_OUT
    assert outcome.records == ()
    assert outcome.error.code == "provider_timeout"
    assert outcome.error.error_type == "ProviderTimeoutError"
    assert outcome.deadline.timeout_seconds == pytest.approx(0.01)
    with pytest.raises(FrozenInstanceError):
        outcome.deadline.timeout_seconds = 1


def test_one_timeout_and_one_success():
    requests = (
        provider_request("slow", FunctionProvider(slow_provider), 0),
        provider_request(
            "fast",
            FunctionProvider(lambda **kwargs: {"results": []}),
            1,
        ),
    )

    outcomes = timeout_executor(max_workers=2).execute(requests)

    assert tuple(outcome.status for outcome in outcomes) == (
        ProviderStatus.TIMED_OUT,
        ProviderStatus.SUCCESS,
    )


def test_all_timeout_returns_empty_result_and_preserves_outcomes_and_errors():
    providers = {
        "first": FunctionProvider(slow_provider),
        "second": FunctionProvider(slow_provider),
    }

    result = timeout_engine(providers).search(
        query="topic", providers=["first", "second"]
    )

    assert result.publications == ()
    assert result.timed_out_providers == ("first", "second")
    assert tuple(outcome.provider_id for outcome in result.provider_outcomes) == (
        "first",
        "second",
    )
    assert tuple(result.errors) == ("first", "second")


def test_timeout_preserves_provider_ordering():
    requests = (
        provider_request("slow", FunctionProvider(slow_provider), 0),
        provider_request(
            "fast",
            FunctionProvider(lambda **kwargs: {"results": []}),
            1,
        ),
    )

    outcomes = timeout_executor(max_workers=2).execute(requests)

    assert tuple(outcome.provider_id for outcome in outcomes) == ("slow", "fast")


def test_timeout_produces_partial_result():
    result = timeout_engine({"slow": FunctionProvider(slow_provider)}).search(
        query="topic", providers=["slow"]
    )

    assert result.partial is True


def test_timeout_does_not_affect_successful_provider_publications():
    providers = {
        "slow": FunctionProvider(slow_provider),
        "fast": FunctionProvider(lambda **kwargs: {
            "results": [{"doi": "kept", "title": "Kept"}]
        }),
    }

    result = timeout_engine(providers).search(
        query="topic", providers=["slow", "fast"]
    )

    assert result.successful_providers == ("fast",)
    assert tuple(publication["title"] for publication in result.publications) == (
        "Kept",
    )


def test_one_provider_timeout_returns_without_raising():
    result = timeout_engine({"slow": FunctionProvider(slow_provider)}).search(
        query="topic", providers=["slow"]
    )

    assert isinstance(result, SearchResult)
    assert result.final_count == 0
    assert result.timed_out_providers == ("slow",)


def test_search_result_contract_is_unchanged_by_timeouts():
    result = timeout_engine({"slow": FunctionProvider(slow_provider)}).search(
        query="topic", providers=["slow"]
    )

    assert tuple(field.name for field in fields(SearchResult)) == (
        "query",
        "providers",
        "publications",
        "provider_outcomes",
        "successful_providers",
        "failed_providers",
        "timed_out_providers",
        "cancelled_providers",
        "partial",
        "raw_count",
        "final_count",
        "sort_mode",
        "errors",
        "planned_queries",
        "duplicates_removed",
    )
    assert result.results is result.publications
    assert result.count == result.final_count


def test_timeout_returns_before_running_provider_is_released():
    started = Event()
    release = Event()

    def blocked_provider(**kwargs):
        started.set()
        assert release.wait(timeout=1)
        return {"results": []}

    try:
        before = monotonic()
        outcome = timeout_executor(timeout=0.02).execute((
            provider_request("blocked", FunctionProvider(blocked_provider)),
        ))[0]
        elapsed = monotonic() - before

        assert started.is_set()
        assert not release.is_set()
        assert elapsed < 0.2
        assert outcome.status is ProviderStatus.TIMED_OUT
    finally:
        release.set()


def test_queued_timed_out_provider_is_cancelled_before_starting():
    first_started = Event()
    release_first = Event()
    second_called = Event()

    def first_provider(**kwargs):
        first_started.set()
        assert release_first.wait(timeout=1)
        return {"results": []}

    def second_provider(**kwargs):
        second_called.set()
        return {"results": []}

    requests = (
        provider_request("first", FunctionProvider(first_provider), 0),
        provider_request("second", FunctionProvider(second_provider), 1),
    )

    try:
        outcomes = timeout_executor(timeout=0.02, max_workers=1).execute(requests)

        assert first_started.is_set()
        assert not release_first.is_set()
        assert not second_called.is_set()
        assert tuple(outcome.provider_id for outcome in outcomes) == (
            "first",
            "second",
        )
        assert all(
            outcome.status is ProviderStatus.TIMED_OUT
            for outcome in outcomes
        )
    finally:
        release_first.set()
