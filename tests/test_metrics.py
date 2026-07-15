from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from research_engine.metrics import MetricsCollector, NullMetricsCollector
from research_engine.query_cache import CacheKey, QueryCache
from research_engine.search_engine import SearchEngine
from research_engine.search_executor import SearchExecutor
from research_engine.search_models import (
    ExecutionPolicy,
    ProviderOutcome,
    ProviderRequest,
    ProviderStatus,
    RetryPolicy,
    SearchResult,
)


def counter(snapshot, name):
    return snapshot.counters.get(name).value if name in snapshot.counters else 0


def test_concurrent_counter_updates_are_not_lost():
    metrics = MetricsCollector()

    def update(_: int) -> None:
        for _ in range(1_000):
            metrics.increment("requests")

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(update, range(8)))

    assert counter(metrics.snapshot(), "requests") == 8_000


def test_concurrent_histogram_observations_are_not_lost():
    metrics = MetricsCollector()

    def observe(index: int) -> None:
        metrics.observe("latency", index)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(observe, range(1_000)))

    histogram = metrics.snapshot().histograms["latency"]
    assert histogram.count == 1_000
    assert histogram.sum == 499_500
    assert histogram.min == 0
    assert histogram.max == 999


def test_snapshot_values_and_mappings_are_immutable():
    metrics = MetricsCollector()
    metrics.increment("calls", 3)
    metrics.observe("duration", 1.5)
    metrics.observe("duration", 2.5)

    snapshot = metrics.snapshot()
    assert snapshot.counters["calls"].value == 3
    assert snapshot.histograms["duration"].count == 2
    assert snapshot.histograms["duration"].sum == 4
    assert snapshot.histograms["duration"].min == 1.5
    assert snapshot.histograms["duration"].max == 2.5
    with pytest.raises(TypeError):
        snapshot.counters["other"] = object()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        snapshot.counters["calls"].value = 4  # type: ignore[misc]


def test_null_metrics_collector_is_a_no_op_with_a_stable_empty_snapshot():
    metrics = NullMetricsCollector()
    first = metrics.snapshot()
    metrics.increment("calls")
    metrics.observe("duration", 1.5)

    assert metrics.snapshot() is first
    assert first.counters == {}
    assert first.histograms == {}


def _cache_result() -> SearchResult:
    return SearchResult(
        query="topic",
        providers=("provider",),
        publications=(),
        provider_outcomes=(),
        successful_providers=("provider",),
        failed_providers=(),
        timed_out_providers=(),
        cancelled_providers=(),
        partial=False,
        raw_count=0,
        final_count=0,
        sort_mode="relevance",
        errors=MappingProxyType({}),
        planned_queries=MappingProxyType({}),
        duplicates_removed=0,
    )


def _cache_key(query: str) -> CacheKey:
    return CacheKey(query, ("provider",), 20, None, None, "relevance")


def test_query_cache_records_hits_misses_insertions_evictions_and_expirations():
    metrics = MetricsCollector()
    now = [0.0]
    cache = QueryCache(max_entries=1, ttl_seconds=1, clock=lambda: now[0], metrics=metrics)
    first, second = _cache_key("first"), _cache_key("second")

    assert cache.get(first) is None
    cache.set(first, _cache_result())
    assert cache.get(first) is not None
    cache.set(second, _cache_result())
    now[0] = 2
    assert cache.get(second) is None

    snapshot = metrics.snapshot()
    assert counter(snapshot, "cache_hits") == 1
    assert counter(snapshot, "cache_misses") == 2
    assert counter(snapshot, "cache_insertions") == 2
    assert counter(snapshot, "cache_evictions") == 1
    assert counter(snapshot, "cache_expirations") == 1


class _FunctionProvider:
    def __init__(self, function):
        self.search = function


def _request(provider: _FunctionProvider) -> ProviderRequest:
    return ProviderRequest(
        provider_id="provider", original_query="topic", planned_query="topic",
        max_results=20, from_year=None, until_year=None, ordinal=0, provider=provider,
    )


def test_search_executor_records_requests_terminal_outcomes_and_retries():
    metrics = MetricsCollector()
    responses = iter((ConnectionError("temporary"), {"results": []}))
    provider = _FunctionProvider(lambda **_: _raise_or_return(next(responses)))
    executor = SearchExecutor(
        ExecutionPolicy(retry_policy=RetryPolicy(max_attempts=2, initial_backoff=0)),
        metrics=metrics,
    )

    outcome = executor.execute((_request(provider),))[0]

    assert outcome.status is ProviderStatus.SUCCESS
    snapshot = metrics.snapshot()
    assert counter(snapshot, "provider_requests") == 2
    assert counter(snapshot, "provider_successes") == 1
    assert counter(snapshot, "provider_failures") == 0
    assert counter(snapshot, "provider_timeouts") == 0
    assert counter(snapshot, "retries") == 1
    assert counter(snapshot, "retry_successes") == 1


def _raise_or_return(value):
    if isinstance(value, Exception):
        raise value
    return value


class _ProviderManager:
    def get(self, provider_id):
        return {"id": provider_id, "enabled": True}

    def list_enabled(self):
        return [{"id": "provider", "enabled": True}]


class _Registry:
    def get_optional(self, provider_id):
        return object()


class _Executor:
    def execute(self, requests):
        request = tuple(requests)[0]
        return (ProviderOutcome(
            provider_id=request.provider_id, status=ProviderStatus.SUCCESS,
            original_query=request.original_query, planned_query=request.planned_query,
            records=({"provider": "provider", "title": "topic", "doi": "10/example"},), attempt_count=1,
            elapsed_ms=0, error=None, ordinal=request.ordinal,
        ),)


def test_search_engine_records_search_and_publication_metrics():
    metrics = MetricsCollector()
    engine = SearchEngine(
        provider_manager=_ProviderManager(), provider_registry=_Registry(),
        executor=_Executor(), metrics=metrics,
    )

    engine.search("topic", providers=["provider"])
    engine.search("topic", providers=["provider"])

    snapshot = metrics.snapshot()
    assert counter(snapshot, "searches") == 2
    assert counter(snapshot, "completed_searches") == 2
    assert counter(snapshot, "partial_searches") == 0
    assert counter(snapshot, "raw_publications") == 1
    assert counter(snapshot, "fused_publications") == 1
    assert counter(snapshot, "duplicates_removed") == 0
    assert snapshot.histograms["search_duration_seconds"].count == 2
