from collections import OrderedDict

from research_engine.fusion_engine import FusionEngine
from research_engine.search_engine import SearchEngine


class FakeProvider:
    def __init__(self, response):
        self.response = response

    def search(self, **kwargs):
        return self.response


class FakeRegistry:
    def __init__(self, providers):
        self.providers = providers

    def get_optional(self, provider_id):
        return self.providers.get(provider_id)


class FakeProviderManager:
    def __init__(self, provider_ids):
        self.configurations = OrderedDict(
            (provider_id, {"id": provider_id, "enabled": True})
            for provider_id in provider_ids
        )

    def get(self, provider_id):
        return self.configurations.get(provider_id)

    def list_enabled(self):
        return list(self.configurations.values())


class RecordingFusionEngine:
    def __init__(self):
        self.engine = FusionEngine()
        self.records = []

    def merge(self, existing, new):
        self.records.append(new)
        return self.engine.merge(existing, new)


class RecordingRanker:
    def __init__(self, fusion):
        self.fusion = fusion
        self.received = None

    def rank(self, publications, sort_mode):
        self.received = publications
        assert len(self.fusion.records) == 4
        assert all("_record" in publication for publication in publications)
        return publications


def make_engine(provider_responses, fusion_engine=None, ranker=None):
    providers = {
        provider_id: FakeProvider(response)
        for provider_id, response in provider_responses.items()
    }
    return SearchEngine(
        provider_manager=FakeProviderManager(providers),
        provider_registry=FakeRegistry(providers),
        fusion_engine=fusion_engine,
        ranker=ranker,
    )


def test_search_clusters_then_fuses_every_record_before_ranking():
    provider_results = {
        "crossref": [
            {"provider": "crossref", "doi": "10.1000/shared", "title": "Shared"},
            {"provider": "crossref", "doi": "10.1000/distinct", "title": "Distinct"},
        ],
        "openalex": [
            {"provider": "openalex", "doi": "10.1000/shared", "abstract": "OpenAlex abstract"},
        ],
        "scopus": [
            {"provider": "scopus", "doi": "10.1000/shared", "citations": 7},
        ],
    }
    responses = {
        provider_id: {"results": records}
        for provider_id, records in provider_results.items()
    }
    fusion = RecordingFusionEngine()
    ranker = RecordingRanker(fusion)
    engine = make_engine(responses, fusion_engine=fusion, ranker=ranker)

    result = engine.search(
        query="publication",
        providers=["crossref", "openalex", "scopus"],
        sort_mode="none",
    )

    expected_records = [
        *provider_results["crossref"],
        *provider_results["openalex"],
        *provider_results["scopus"],
    ]
    assert sorted(fusion.records, key=repr) == sorted(expected_records, key=repr)
    assert tuple(ranker.received) == result.publications
    assert len(result.publications) == 2
    shared = next(p for p in result.publications if p["doi"] == "10.1000/shared")
    assert shared["_providers"] == ["crossref", "openalex", "scopus"]
    assert result.raw_count == 4
    assert result.duplicates_removed == 2


def test_executor_injects_requested_provider_without_overwriting_item_provider():
    results = [
        {"doi": "10.1000/requested", "title": "Requested provider"},
        {"provider": "item-provider", "doi": "10.1000/item", "title": "Item provider"},
    ]
    engine = make_engine({
        "requested-provider": {
            "provider": "envelope-provider",
            "results": results,
        }
    })

    result = engine.search(query="publication", providers=["requested-provider"])

    outcome_records = result.provider_outcomes[0].records
    assert outcome_records[0]["provider"] == "requested-provider"
    assert outcome_records[1]["provider"] == "item-provider"
    by_doi = {publication["doi"]: publication for publication in result.publications}
    assert by_doi["10.1000/requested"]["_providers"] == ["requested-provider"]
    assert by_doi["10.1000/item"]["_providers"] == ["item-provider"]
