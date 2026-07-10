from research_engine.deduplicator import Deduplicator
from research_engine.fusion_engine import FusionEngine
from research_engine.search_engine import SearchEngine


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


def test_search_all_clusters_then_fuses_every_record_before_ranking():
    provider_results = {
        "crossref": [
            {
                "provider": "crossref",
                "doi": "10.1000/shared",
                "title": "Shared",
            },
            {
                "provider": "crossref",
                "doi": "10.1000/distinct",
                "title": "Distinct",
            },
        ],
        "openalex": [
            {
                "provider": "openalex",
                "doi": "10.1000/shared",
                "abstract": "OpenAlex abstract",
            },
        ],
        "scopus": [
            {
                "provider": "scopus",
                "doi": "10.1000/shared",
                "citations": 7,
            },
        ],
    }
    engine = SearchEngine.__new__(SearchEngine)
    engine.deduplicator = Deduplicator()
    engine.fusion = RecordingFusionEngine()
    engine.ranker = RecordingRanker(engine.fusion)
    engine.search = lambda provider, **kwargs: {
        "planned_query": kwargs["query"],
        "results": provider_results[provider],
    }

    result = engine.search_all(
        query="publication",
        providers=["crossref", "openalex", "scopus"],
        sort_mode="none",
    )

    expected_records = [
        *provider_results["crossref"],
        *provider_results["openalex"],
        *provider_results["scopus"],
    ]
    assert {id(record) for record in engine.fusion.records} == {
        id(record) for record in expected_records
    }
    assert engine.ranker.received == result["results"]
    assert len(result["results"]) == 2
    shared = next(p for p in result["results"] if p["doi"] == "10.1000/shared")
    assert shared["_providers"] == ["crossref", "openalex", "scopus"]
    assert result["raw_count"] == 4
    assert result["duplicates_removed"] == 2


def test_search_all_injects_response_provider_without_overwriting_item_provider():
    provider_results = [
        {"doi": "10.1000/envelope", "title": "Envelope provider"},
        {
            "provider": "item-provider",
            "doi": "10.1000/item",
            "title": "Item provider",
        },
    ]
    engine = SearchEngine.__new__(SearchEngine)
    engine.deduplicator = Deduplicator()
    engine.fusion = FusionEngine()
    engine.ranker = type(
        "PassThroughRanker",
        (),
        {"rank": staticmethod(lambda publications, sort_mode: publications)},
    )()
    engine.search = lambda provider, **kwargs: {
        "provider": "envelope-provider",
        "planned_query": kwargs["query"],
        "results": provider_results,
    }

    result = engine.search_all(query="publication", providers=["requested-provider"])

    by_doi = {publication["doi"]: publication for publication in result["results"]}
    assert by_doi["10.1000/envelope"]["_providers"] == ["envelope-provider"]
    assert by_doi["10.1000/item"]["_providers"] == ["item-provider"]
