from research_engine.fusion_engine import FusionEngine
from research_models.publication import Publication


def test_merge_one_provider_creates_canonical_record_and_flat_projection():
    engine = FusionEngine()

    merged = engine.merge(
        None,
        {
            "provider": "crossref",
            "doi": "10.1000/example",
            "title": "An example",
        },
    )

    assert merged["doi"] == "10.1000/example"
    assert merged["title"] == "An example"
    assert merged["_providers"] == ["crossref"]
    assert merged["_record"]["title"]["selected"] == "An example"
    assert [
        value["provider"]
        for value in merged["_record"]["title"]["values"]
    ] == ["crossref"]


def test_serialized_record_preserves_provenance_quality_and_timestamps():
    engine = FusionEngine()
    publication = Publication()
    publication.add(
        provider="crossref",
        field_name="title",
        value="Short title",
        quality=0.91,
    )
    first_timestamp = publication.fields["title"].values[0].timestamp

    serialized = engine._publication_to_flat_dict(publication)
    serialized["_providers"] = ["crossref"]
    serialized["_record"] = publication.to_dict()

    merged_second = engine.merge(
        serialized,
        {
            "provider": "openalex",
            "title": "A longer example title",
            "abstract": "An abstract from OpenAlex.",
        },
    )
    second_title_value = merged_second["_record"]["title"]["values"][1]
    second_timestamp = second_title_value["timestamp"]

    merged_third = engine.merge(
        merged_second,
        {
            "provider": "scopus",
            "title": "The longest example title from Scopus",
            "citations": 12,
        },
    )

    title_values = merged_third["_record"]["title"]["values"]
    assert [value["provider"] for value in title_values] == [
        "crossref",
        "openalex",
        "scopus",
    ]
    assert title_values[0] == {
        "provider": "crossref",
        "value": "Short title",
        "quality": 0.91,
        "timestamp": first_timestamp,
    }
    assert title_values[1] == {
        "provider": "openalex",
        "value": "A longer example title",
        "quality": None,
        "timestamp": second_timestamp,
    }
    assert merged_third["_record"]["abstract"]["values"][0]["provider"] == "openalex"
    assert merged_third["_record"]["citations"]["values"][0]["provider"] == "scopus"
    assert merged_third["_providers"] == ["crossref", "openalex", "scopus"]
    assert merged_third["title"] == "The longest example title from Scopus"
