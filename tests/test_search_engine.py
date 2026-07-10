from __future__ import annotations

from collections import OrderedDict

import pytest

from research_engine.search_engine import SearchEngine
from research_engine.search_executor import SearchExecutor
from research_engine.search_models import ProviderStatus, SearchResult


class FakeProvider:
    def __init__(self, response=None, error=None):
        self.response = response if response is not None else {"results": []}
        self.error = error
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeRegistry:
    def __init__(self, providers):
        self.providers = providers

    def get_optional(self, provider_id):
        return self.providers.get(provider_id)


class FakeProviderManager:
    def __init__(self, configurations):
        self.configurations = OrderedDict(
            (item["id"], item) for item in configurations
        )

    def get(self, provider_id):
        return self.configurations.get(provider_id)

    def list_enabled(self):
        return [item for item in self.configurations.values() if item["enabled"]]


class RecordingExecutor(SearchExecutor):
    def __init__(self):
        super().__init__()
        self.batches = []

    def execute(self, requests):
        self.batches.append(tuple(requests))
        return super().execute(requests)


def record(title, **values):
    return {"title": title, "doi": values.pop("doi", title), **values}


def make_engine(provider_map, configurations=None, **kwargs):
    if configurations is None:
        configurations = [
            {"id": provider_id, "enabled": True}
            for provider_id in provider_map
        ]
    return SearchEngine(
        provider_manager=FakeProviderManager(configurations),
        provider_registry=FakeRegistry(provider_map),
        **kwargs,
    )


def test_providers_none_uses_all_enabled_in_manager_order():
    providers = {
        "crossref": FakeProvider(),
        "openalex": FakeProvider(),
        "disabled": FakeProvider(),
    }
    engine = make_engine(providers, configurations=[
        {"id": "openalex", "enabled": True},
        {"id": "disabled", "enabled": False},
        {"id": "crossref", "enabled": True},
    ])

    result = engine.search(query="topic", providers=None)

    assert result.providers == ("openalex", "crossref")
    assert result.successful_providers == ("openalex", "crossref")


def test_one_explicit_provider_uses_executor_pipeline():
    executor = RecordingExecutor()
    provider = FakeProvider({"results": [record("one")]})
    engine = make_engine({"crossref": provider}, executor=executor)

    result = engine.search(query="topic", providers=["crossref"])

    assert len(executor.batches) == 1
    assert [item.provider_id for item in executor.batches[0]] == ["crossref"]
    assert result.publications[0]["_providers"] == ["crossref"]


def test_several_explicit_providers_preserve_caller_order():
    engine = make_engine({
        "crossref": FakeProvider(),
        "openalex": FakeProvider(),
    })

    result = engine.search(query="topic", providers=["openalex", "crossref"])

    assert result.providers == ("openalex", "crossref")
    assert tuple(o.provider_id for o in result.provider_outcomes) == result.providers


@pytest.mark.parametrize(
    ("providers", "message"),
    [
        ([], "providers must not be empty"),
        (["crossref", "crossref"], "duplicate provider identifiers: crossref"),
    ],
)
def test_invalid_provider_sequences(providers, message):
    engine = make_engine({"crossref": FakeProvider()})

    with pytest.raises(ValueError, match=message):
        engine.search(query="topic", providers=providers)


@pytest.mark.parametrize(
    ("provider_id", "configurations", "implementations", "code"),
    [
        ("unknown", [], {}, "unknown_provider"),
        ("disabled", [{"id": "disabled", "enabled": False}], {"disabled": FakeProvider()}, "provider_disabled"),
        ("missing", [{"id": "missing", "enabled": True}], {}, "provider_implementation_unavailable"),
    ],
)
def test_provider_resolution_failures_are_distinct_outcomes(
    provider_id, configurations, implementations, code
):
    engine = make_engine(implementations, configurations=configurations)

    result = engine.search(query="topic", providers=[provider_id])

    outcome = result.provider_outcomes[0]
    assert outcome.status is ProviderStatus.FAILED
    assert outcome.error.code == code
    assert outcome.attempt_count == 0


def test_successful_provider_returns_search_result():
    engine = make_engine({
        "crossref": FakeProvider({"results": [record("dynamic line rating")]})
    })

    result = engine.search(query="topic", providers=["crossref"])

    assert isinstance(result, SearchResult)
    assert result.successful_providers == ("crossref",)
    assert result.failed_providers == ()
    assert result.raw_count == 1
    assert result.final_count == 1
    assert result["results"] == list(result.publications)


def test_blank_provider_attribution_is_injected():
    engine = make_engine({
        "crossref": FakeProvider({
            "results": [record("one", provider=None)],
        })
    })

    result = engine.search(query="topic", providers=["crossref"])

    assert result.provider_outcomes[0].records[0]["provider"] == "crossref"


def test_provider_exception_is_a_failed_outcome():
    engine = make_engine({"crossref": FakeProvider(error=RuntimeError("down"))})

    result = engine.search(query="topic", providers=["crossref"])

    assert result.failed_providers == ("crossref",)
    assert result.provider_outcomes[0].attempt_count == 1
    assert result.errors == {"crossref": "down"}


def test_partial_success_keeps_successful_records():
    engine = make_engine({
        "good": FakeProvider({"results": [record("kept")]}),
        "bad": FakeProvider(error=RuntimeError("failed")),
    })

    result = engine.search(query="topic", providers=["good", "bad"])

    assert result.partial is True
    assert result.successful_providers == ("good",)
    assert result.failed_providers == ("bad",)
    assert [item["title"] for item in result.publications] == ["kept"]


def test_all_providers_fail_without_raising():
    engine = make_engine({
        "one": FakeProvider(error=RuntimeError("one failed")),
        "two": FakeProvider(error=RuntimeError("two failed")),
    })

    result = engine.search(query="topic", providers=["one", "two"])

    assert result.publications == ()
    assert result.failed_providers == ("one", "two")
    assert result.partial is False


def test_empty_result_is_successful():
    engine = make_engine({"empty": FakeProvider({"results": []})})

    result = engine.search(query="topic", providers=["empty"])

    assert result.successful_providers == ("empty",)
    assert result.raw_count == 0


@pytest.mark.parametrize("response", [None, {}, {"results": {}}, {"results": ["bad"]}])
def test_malformed_provider_response_is_failed(response):
    provider = FakeProvider()
    provider.response = response
    engine = make_engine({"bad": provider})

    result = engine.search(query="topic", providers=["bad"])

    assert result.provider_outcomes[0].error.code == "invalid_provider_response"


def test_provider_and_record_order_are_deterministic():
    engine = make_engine({
        "second": FakeProvider({"results": [record("b"), record("a")]}),
        "first": FakeProvider({"results": [record("c")]}),
    })

    result = engine.search(
        query="topic",
        providers=["second", "first"],
        sort_mode="none",
    )

    assert [o.provider_id for o in result.provider_outcomes] == ["second", "first"]
    assert [p["title"] for p in result.publications] == ["a", "b", "c"]


def test_one_and_multiple_providers_use_the_same_executor():
    executor = RecordingExecutor()
    engine = make_engine({
        "one": FakeProvider(),
        "two": FakeProvider(),
    }, executor=executor)

    engine.search(query="topic", providers=["one"])
    engine.search(query="topic", providers=["one", "two"])

    assert [len(batch) for batch in executor.batches] == [1, 2]


def test_current_deduplication_and_ranking_pipeline_remains_active():
    engine = make_engine({
        "first": FakeProvider({"results": [
            record("other", doi="same", citations=1),
            record("dynamic line rating", doi="best", citations=0),
        ]}),
        "second": FakeProvider({"results": [
            record("replacement", doi="same", citations=10),
        ]}),
    })

    result = engine.search(query="topic", providers=["first", "second"])

    assert result.duplicates_removed == 1
    assert result.publications[0]["title"] == "dynamic line rating"
    assert any(p["title"] == "replacement" for p in result.publications)
    assert all("score" in p for p in result.publications)


def test_search_all_is_only_a_deprecated_delegate(monkeypatch):
    engine = make_engine({"one": FakeProvider()})
    sentinel = object()
    calls = []

    def fake_search(**kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(engine, "search", fake_search)

    with pytest.deprecated_call(match="search_all"):
        result = engine.search_all(query="topic", providers=["one"])

    assert result is sentinel
    assert calls == [{
        "query": "topic",
        "providers": ["one"],
        "max_results": 20,
        "from_year": None,
        "until_year": None,
        "sort_mode": "score",
    }]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"query": "  "}, "query must be"),
        ({"query": "x", "max_results": 0}, "max_results"),
        ({"query": "x", "from_year": 2026, "until_year": 2020}, "from_year"),
        ({"query": "x", "sort_mode": "random"}, "unsupported sort_mode"),
    ],
)
def test_search_request_validation(kwargs, message):
    engine = make_engine({"one": FakeProvider()})

    with pytest.raises(ValueError, match=message):
        engine.search(providers=["one"], **kwargs)
