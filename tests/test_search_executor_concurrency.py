from __future__ import annotations

import random
from dataclasses import fields
from threading import Barrier, Event, Lock, Thread
from time import sleep

from research_engine.search_engine import SearchEngine
from research_engine.search_executor import SearchExecutor
from research_engine.search_models import ProviderRequest, SearchResult
from tests.test_search_engine import FakeProviderManager, FakeRegistry


class FunctionProvider:
    def __init__(self, search):
        self.search = search


def request(provider_id, provider, ordinal):
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


def engine_for(providers, max_workers=8):
    configurations = [
        {"id": provider_id, "enabled": True}
        for provider_id in providers
    ]
    return SearchEngine(
        provider_manager=FakeProviderManager(configurations),
        provider_registry=FakeRegistry(providers),
        executor=SearchExecutor(max_workers=max_workers),
    )


def test_two_providers_execute_concurrently():
    barrier = Barrier(2, timeout=1)

    def search(**kwargs):
        barrier.wait()
        return {"results": []}

    requests = tuple(
        request(str(index), FunctionProvider(search), index)
        for index in range(2)
    )

    outcomes = SearchExecutor(max_workers=2).execute(requests)

    assert [outcome.provider_id for outcome in outcomes] == ["0", "1"]


def test_max_workers_is_respected():
    release = Event()
    two_started = Event()
    lock = Lock()
    active = 0
    peak = 0

    def search(**kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 2:
                two_started.set()
        assert release.wait(timeout=1)
        with lock:
            active -= 1
        return {"results": []}

    requests = tuple(
        request(str(index), FunctionProvider(search), index)
        for index in range(5)
    )
    done = Event()

    def execute():
        SearchExecutor(max_workers=2).execute(requests)
        done.set()

    thread = Thread(target=execute)
    thread.start()
    assert two_started.wait(timeout=1)
    assert peak == 2
    release.set()
    thread.join(timeout=1)
    assert done.is_set()
    assert peak == 2


def test_one_provider_search_uses_executor_path():
    called = Event()

    def search(**kwargs):
        called.set()
        return {"results": [{"doi": "one", "title": "One"}]}

    result = engine_for({"one": FunctionProvider(search)}, max_workers=4).search(
        query="topic", providers=["one"]
    )

    assert called.is_set()
    assert result.successful_providers == ("one",)
    assert [publication["title"] for publication in result.publications] == ["One"]


def test_outcome_order_follows_request_order_when_completion_is_reversed():
    first_started = Event()
    allow_first = Event()

    def first(**kwargs):
        first_started.set()
        assert allow_first.wait(timeout=1)
        return {"results": []}

    def second(**kwargs):
        assert first_started.wait(timeout=1)
        allow_first.set()
        return {"results": []}

    requests = (
        request("first", FunctionProvider(first), 0),
        request("second", FunctionProvider(second), 1),
    )

    outcomes = SearchExecutor(max_workers=2).execute(requests)

    assert [outcome.provider_id for outcome in outcomes] == ["first", "second"]


def test_publications_are_deterministic_despite_randomized_delays():
    def provider(records):
        def search(**kwargs):
            sleep(random.uniform(0, 0.005))
            return {"results": records}

        return FunctionProvider(search)

    providers = {
        "first": provider([
            {"provider": "first", "doi": "shared", "title": "Shared"},
            {"provider": "first", "doi": "first", "title": "First"},
        ]),
        "second": provider([
            {"provider": "second", "doi": "shared", "citations": 10},
            {"provider": "second", "doi": "second", "title": "Second"},
        ]),
    }
    engine = engine_for(providers)

    publications = []
    for _ in range(10):
        result = engine.search(
            query="topic", providers=["first", "second"], sort_mode="none"
        )
        publications.append(tuple(
            (
                publication["doi"],
                publication.get("title"),
                publication.get("citations"),
                tuple(publication["_providers"]),
            )
            for publication in result.publications
        ))

    assert all(result == publications[0] for result in publications)


def test_provider_failure_does_not_discard_successful_results():
    def fail(**kwargs):
        raise RuntimeError("down")

    providers = {
        "bad": FunctionProvider(fail),
        "good": FunctionProvider(lambda **kwargs: {
            "results": [{"doi": "kept", "title": "Kept"}]
        }),
    }

    result = engine_for(providers).search(query="topic", providers=["bad", "good"])

    assert result.partial is True
    assert result.failed_providers == ("bad",)
    assert result.successful_providers == ("good",)
    assert [publication["title"] for publication in result.publications] == ["Kept"]


def test_search_result_shape_is_unchanged():
    provider = FunctionProvider(lambda **kwargs: {"results": []})

    result = engine_for({"one": provider}).search(query="topic", providers=["one"])

    assert isinstance(result, SearchResult)
    assert tuple(result.to_dict()) == (
        "query",
        "providers",
        "publications",
        "results",
        "provider_outcomes",
        "successful_providers",
        "failed_providers",
        "timed_out_providers",
        "cancelled_providers",
        "partial",
        "raw_count",
        "final_count",
        "count",
        "sort_mode",
        "errors",
        "planned_queries",
        "duplicates_removed",
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
