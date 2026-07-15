from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

import research_config.db as config_db
from research_config.db import init_db
from research_config.providers import delete_provider, upsert_provider
from research_engine.query_cache import (
    CacheKey,
    QueryCache,
)
from research_engine.search_models import ProviderOutcome, ProviderStatus, SearchResult


def make_key(query: str) -> CacheKey:
    return CacheKey(
        query=query,
        providers=("crossref",),
        max_results=20,
        from_year=None,
        until_year=None,
        sort_mode="relevance",
    )


def make_result(
    query: str,
    *,
    partial: bool = False,
    failed: tuple[str, ...] = (),
    timed_out: tuple[str, ...] = (),
) -> SearchResult:
    return SearchResult(
        query=query,
        providers=("crossref",),
        publications=({"title": query, "metadata": {"source": "original"}},),
        provider_outcomes=(
            ProviderOutcome(
                provider_id="crossref",
                status=ProviderStatus.SUCCESS,
                original_query=query,
                planned_query=query,
                records=({"title": query, "metadata": {"source": "original"}},),
                attempt_count=1,
                elapsed_ms=0,
                error=None,
                ordinal=0,
            ),
        ),
        successful_providers=() if failed or timed_out else ("crossref",),
        failed_providers=failed,
        timed_out_providers=timed_out,
        cancelled_providers=(),
        partial=partial,
        raw_count=0,
        final_count=0,
        sort_mode="relevance",
        errors=MappingProxyType({}),
        planned_queries=MappingProxyType({}),
        duplicates_removed=0,
    )


def test_cache_key_is_immutable_and_hashable():
    key = make_key("topic")

    assert {key: "value"}[key] == "value"
    with pytest.raises(FrozenInstanceError):
        key.query = "other"  # type: ignore[misc]


def test_cache_key_canonicalizes_provider_sequences_to_an_immutable_tuple():
    key = CacheKey("topic", ["crossref"], 20, None, None, "relevance")

    assert key.providers == ("crossref",)
    assert isinstance(hash(key), int)


def test_expired_entry_is_not_returned():
    now = [10.0]
    cache = QueryCache(ttl_seconds=5, clock=lambda: now[0])
    key = make_key("topic")
    result = make_result("topic")

    cache.set(key, result)
    now[0] = 14.999
    assert cache.get(key) == result
    now[0] = 15.0
    assert cache.get(key) is None


def test_lru_eviction_touches_entries_on_read():
    cache = QueryCache(max_entries=2)
    first, second, third = (make_key(name) for name in ("first", "second", "third"))
    first_result = make_result("first")
    second_result = make_result("second")

    cache.set(first, first_result)
    cache.set(second, second_result)
    assert cache.get(first) == first_result
    cache.set(third, make_result("third"))

    assert cache.get(first) == first_result
    assert cache.get(second) is None
    assert cache.get(third) is not None


def test_partial_results_are_not_stored_directly():
    cache = QueryCache()
    partial = make_result("topic", partial=True)

    cache.set(make_key("topic"), partial)

    assert cache.get(make_key("topic")) is None


def test_failed_results_are_not_stored():
    cache = QueryCache()
    failed = make_result("topic", failed=("crossref",))

    cache.set(make_key("topic"), failed)

    assert cache.get(make_key("topic")) is None


def test_timed_out_results_are_not_stored():
    cache = QueryCache()
    timed_out = make_result("topic", partial=True, timed_out=("crossref",))

    cache.set(make_key("topic"), timed_out)

    assert cache.get(make_key("topic")) is None


def test_cached_results_are_isolated_from_caller_mutation():
    cache = QueryCache()
    key = make_key("topic")
    original = make_result("topic")

    cache.set(key, original)
    original.publications[0]["metadata"]["source"] = "caller mutation"
    original.provider_outcomes[0].records[0]["metadata"]["source"] = "caller mutation"
    first = cache.get(key)
    first.publications[0]["metadata"]["source"] = "cached caller mutation"
    first.provider_outcomes[0].records[0]["metadata"]["source"] = "cached caller mutation"
    second = cache.get(key)

    assert first is not second
    assert second.publications[0]["metadata"]["source"] == "original"
    assert second.provider_outcomes[0].records[0]["metadata"]["source"] == "original"


def test_provider_configuration_mutations_invalidate_cache_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(config_db, "DB_PATH", tmp_path / "providers.db")
    init_db()
    cache = QueryCache()
    first_key = make_key("topic")
    cache.set(first_key, make_result("topic"))

    upsert_provider({
        "id": "crossref",
        "name": "Crossref",
        "type": "bibliographic",
        "enabled": True,
    })
    second_key = make_key("topic")

    assert second_key.configuration_version != first_key.configuration_version
    assert cache.get(second_key) is None

    cache.set(second_key, make_result("topic"))
    delete_provider("crossref")
    third_key = make_key("topic")

    assert third_key.configuration_version != second_key.configuration_version
    assert cache.get(third_key) is None


@pytest.mark.parametrize(
    ("kwargs", "exception"),
    [
        ({"max_entries": 0}, ValueError),
        ({"max_entries": True}, TypeError),
        ({"ttl_seconds": -1}, ValueError),
        ({"ttl_seconds": True}, TypeError),
    ],
)
def test_cache_configuration_is_validated(kwargs, exception):
    with pytest.raises(exception):
        QueryCache(**kwargs)


def test_concurrent_access_is_safe():
    cache = QueryCache(max_entries=64)

    def put_and_get(index: int) -> SearchResult | None:
        key = make_key(str(index))
        result = make_result(str(index))
        cache.set(key, result)
        return cache.get(key)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(put_and_get, range(64)))

    assert all(result is not None for result in results)
