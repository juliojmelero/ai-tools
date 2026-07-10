import json

import research_cache.cache_manager as cache_module
import research_config.db as config_db
from research_cache.cache_manager import CacheManager
from research_config.db import init_db
from research_config.providers import upsert_provider
from research_engine.fusion_engine import FusionEngine
from research_engine.ranking import Ranker
from research_engine.search_engine import SearchEngine
from research_models.publication import Publication


def assert_publications_semantically_equal(actual, expected):
    """Compare canonical content, including observation history, not identity."""
    assert isinstance(actual, Publication)
    assert isinstance(expected, Publication)
    assert actual.to_dict()["_schema_version"] == expected.to_dict()[
        "_schema_version"
    ]

    for field_name in actual.fields:
        actual_field = actual.fields[field_name]
        expected_field = expected.fields[field_name]
        assert actual_field.selected == expected_field.selected
        assert actual_field.merge_strategy == expected_field.merge_strategy
        assert actual_field.selected_provider() == expected_field.selected_provider()
        assert actual_field.contributors() == expected_field.contributors()
        assert sorted(
            (value.provider, value.value, value.quality, value.timestamp, value.current)
            for value in actual_field.values
        ) == sorted(
            (value.provider, value.value, value.quality, value.timestamp, value.current)
            for value in expected_field.values
        )


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_complete_research_pipeline_round_trip_and_second_fusion(
    monkeypatch, tmp_path
):
    doi = "10.1234/dynamic-line-rating"
    title = "Dynamic Line Rating for Resilient Transmission Grids"
    timestamps = {
        "crossref_old": "2025-01-01T00:00:00Z",
        "crossref_new": "2025-02-01T00:00:00Z",
        "openalex": "2025-01-15T00:00:00Z",
        "scopus": "2025-01-20T00:00:00Z",
        "scopus_refresh": "2025-03-01T00:00:00Z",
    }

    monkeypatch.setattr(config_db, "DB_PATH", tmp_path / "providers.db")
    monkeypatch.setattr(cache_module, "CACHE_DB", tmp_path / "cache.db")
    monkeypatch.setenv("SCOPUS_API_KEY", "integration-test-key")
    init_db()
    for provider in ("crossref", "openalex", "scopus"):
        upsert_provider(
            {
                "id": provider,
                "name": provider.title(),
                "type": "bibliographic",
                "enabled": True,
            }
        )

    crossref_items = [
        {
            "DOI": doi,
            "title": [title],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "container-title": ["Grid Research"],
            "publisher": "Old Publisher",
            "is-referenced-by-count": 8,
            "quality": 0.70,
            "timestamp": timestamps["crossref_old"],
        },
        {
            "DOI": doi,
            "title": [title],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "container-title": ["Grid Research"],
            "publisher": "Canonical Publisher",
            "is-referenced-by-count": 12,
            "quality": 0.75,
            "timestamp": timestamps["crossref_new"],
        },
        {
            "DOI": doi,
            "title": [title],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "container-title": ["Grid Research"],
            "publisher": "Canonical Publisher",
            "is-referenced-by-count": 12,
            "quality": 0.95,
            "timestamp": timestamps["crossref_new"],
        },
    ]
    openalex_items = [
        {
            # Deliberately no DOI: the normalized title must bridge this result
            # into the DOI cluster created by Crossref and Scopus.
            "display_name": title,
            "authorships": [
                {"author": {"display_name": "Grace Hopper"}}
            ],
            "primary_location": {
                "source": {"display_name": "Open Grid Journal"},
                "pdf_url": "https://example.test/paper.pdf",
            },
            "concepts": [{"display_name": "Power engineering"}],
            "cited_by_count": 21,
            "quality": 0.99,
            "timestamp": timestamps["openalex"],
        }
    ]
    scopus_items = [
        {
            "prism:doi": doi,
            "dc:title": title,
            "dc:creator": "Katherine Johnson",
            "prism:publicationName": "Scopus Grid Letters",
            "citedby-count": "21",
            "quality": 0.80,
            "timestamp": timestamps["scopus"],
        }
    ]

    def fake_get(url, **kwargs):
        if "crossref" in url:
            return _Response({"message": {"items": crossref_items}})
        if "openalex" in url:
            return _Response({"results": openalex_items})
        assert "elsevier" in url
        return _Response({"search-results": {"entry": scopus_items}})

    monkeypatch.setattr("requests.get", fake_get)

    engine = SearchEngine()
    result = engine.search_all(
        query="dynamic line rating",
        providers=["crossref", "openalex", "scopus"],
        max_results=10,
    )

    assert result["raw_count"] == 5
    assert result["duplicates_removed"] == 4
    assert result["count"] == len(result["results"]) == 1
    canonical = result["results"][0]
    assert canonical["_providers"] == ["crossref", "openalex", "scopus"]
    assert canonical["_schema_version"] == 1
    assert canonical["publisher"] == "Canonical Publisher"
    assert canonical["journal"] == "Grid Research"  # Crossref has priority.
    assert canonical["citations"] == 21
    # Equal maximum citation values select Scopus by provider priority despite
    # OpenAlex's higher quality.
    assert canonical["_record"]["citations"]["selected_provider"] == "scopus"

    crossref_publishers = [
        item
        for item in canonical["_record"]["publisher"]["values"]
        if item["provider"] == "crossref"
    ]
    assert [item["quality"] for item in crossref_publishers] == [
        0.70,
        0.75,
        0.95,
    ]
    assert [item["timestamp"] for item in crossref_publishers] == [
        timestamps["crossref_old"],
        timestamps["crossref_new"],
        timestamps["crossref_new"],
    ]
    # At the same provider timestamp, canonical ordering retains both history
    # entries and makes the higher-quality observation current.
    assert [item["current"] for item in crossref_publishers] == [
        False,
        False,
        True,
    ]
    assert canonical["_record"]["authors"]["contributors"] == [
        "crossref",
        "openalex",
        "scopus",
    ]

    serialized_once = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    serialized_twice = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    assert serialized_once.encode() == serialized_twice.encode()

    cache = CacheManager()
    cache.init_db()
    cache.save_publications([canonical])
    reloaded_dict = cache.get_publication(doi)
    reloaded = Publication.from_dict(reloaded_dict)
    assert_publications_semantically_equal(
        reloaded, Publication.from_dict(canonical)
    )
    assert reloaded_dict["_schema_version"] == 1

    refresh = {
        "provider": "scopus",
        "doi": doi,
        "title": title,
        "citations": 34,
        "quality": 0.98,
        "timestamp": timestamps["scopus_refresh"],
    }
    observation_counts_before_refresh = {
        field_name: len(canonical["_record"][field_name]["values"])
        for field_name in ("doi", "title", "citations")
    }
    second_fused = FusionEngine().merge(reloaded_dict, refresh)

    expected = Publication.from_dict(canonical)
    for field_name in ("doi", "title", "citations"):
        expected.add(
            "scopus",
            field_name,
            refresh[field_name],
            quality=refresh["quality"],
            timestamp=refresh["timestamp"],
        )
    assert_publications_semantically_equal(
        Publication.from_dict(second_fused), expected
    )
    assert second_fused["_schema_version"] == 1
    assert second_fused["_providers"] == ["crossref", "openalex", "scopus"]
    assert second_fused["citations"] == 34
    for field_name, previous_count in observation_counts_before_refresh.items():
        assert len(second_fused["_record"][field_name]["values"]) == (
            previous_count + 1
        )
    scopus_citations = [
        item
        for item in second_fused["_record"]["citations"]["values"]
        if item["provider"] == "scopus"
    ]
    assert len(scopus_citations) == 2
    assert [item["current"] for item in scopus_citations] == [False, True]
    assert scopus_citations[-1]["quality"] == refresh["quality"]
    assert scopus_citations[-1]["timestamp"] == refresh["timestamp"]

    lower_ranked = FusionEngine().merge(
        None,
        {
            "provider": "crossref",
            "doi": "10.1234/lower-ranked",
            "title": "Transmission Line Survey",
            "citations": 0,
            "quality": 0.9,
            "timestamp": "2025-03-01T00:00:00Z",
        },
    )
    ranked = Ranker().rank([lower_ranked, second_fused], sort_mode="score")
    assert [publication["doi"] for publication in ranked] == [
        doi,
        "10.1234/lower-ranked",
    ]
