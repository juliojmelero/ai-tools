from research_engine.provider_result import provider_result
from research_models.converters import (
    crossref_to_publication,
    openalex_to_publication,
    scopus_to_publication,
)


def test_provider_result_schema_accepts_optional_quality_and_timestamp():
    result = provider_result(
        "example", quality=0.8, timestamp="2026-01-01T00:00:00Z", title="Title"
    )

    assert result == {
        "provider": "example",
        "quality": 0.8,
        "timestamp": "2026-01-01T00:00:00Z",
        "title": "Title",
    }


def test_provider_result_schema_omits_missing_optional_metadata_and_unknown_fields():
    result = provider_result("example", title="Title", source_rank=4)

    assert result == {"provider": "example", "title": "Title"}


def test_bundled_converters_remain_compatible_without_quality():
    results = [
        crossref_to_publication({"title": ["Crossref"]}),
        openalex_to_publication({"display_name": "OpenAlex"}),
        scopus_to_publication({"dc:title": "Scopus"}),
    ]

    assert [(result["provider"], result["title"]) for result in results] == [
        ("crossref", "Crossref"),
        ("openalex", "OpenAlex"),
        ("scopus", "Scopus"),
    ]
    assert all("quality" not in result for result in results)


def test_every_bundled_converter_may_emit_quality():
    results = [
        crossref_to_publication({"title": ["Crossref"], "quality": 0.1}),
        openalex_to_publication({"display_name": "OpenAlex", "quality": 0.2}),
        scopus_to_publication({"dc:title": "Scopus", "quality": 0.3}),
    ]

    assert [result["quality"] for result in results] == [0.1, 0.2, 0.3]
