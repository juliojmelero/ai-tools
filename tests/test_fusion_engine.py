import pytest

from research_engine.fusion_engine import FusionEngine
from research_engine.merge_strategies import FusionConfigurationError
from research_models.field_value import FieldValue
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


def _fuse(records):
    engine = FusionEngine()
    merged = None
    for record in records:
        merged = engine.merge(merged, record)
    return merged


def test_reversing_provider_input_keeps_scalar_and_union_selection():
    records = [
        {
            "provider": "openalex",
            "doi": "openalex-doi",
            "title": "A much longer title",
            "citations": 8,
            "authors": ["OpenAlex Author", "Shared Author"],
        },
        {
            "provider": "crossref",
            "doi": "crossref-doi",
            "title": "Short",
            "citations": 3,
            "authors": ["Crossref Author", "Shared Author"],
        },
    ]

    forward = _fuse(records)
    reverse = _fuse(reversed(records))

    for field in ("doi", "title", "citations", "authors"):
        assert forward[field] == reverse[field]
    assert forward["doi"] == "crossref-doi"
    assert forward["authors"] == [
        "Crossref Author",
        "Shared Author",
        "OpenAlex Author",
    ]
    assert forward["_record"]["authors"]["contributors"] == [
        "crossref",
        "openalex",
    ]


def test_equal_length_uses_field_provider_priority():
    merged = _fuse([
        {"provider": "openalex", "title": "Open title"},
        {"provider": "crossref", "title": "Crossref!!"},
    ])

    assert len("Open title") == len("Crossref!!")
    assert merged["title"] == "Crossref!!"
    assert merged["_record"]["title"]["selected_provider"] == "crossref"


def test_equal_maximum_uses_field_provider_priority():
    merged = _fuse([
        {"provider": "openalex", "citations": 12},
        {"provider": "scopus", "citations": 12},
    ])

    assert merged["citations"] == 12
    assert merged["_record"]["citations"]["selected_provider"] == "scopus"


def test_overwrite_uses_provider_priority_instead_of_arrival_order():
    field = FieldValue(merge_strategy="overwrite")
    field.add("openalex", "openalex value", provider_order=["crossref", "openalex"])
    field.add("crossref", "crossref value", provider_order=["crossref", "openalex"])

    assert field.selected == "crossref value"
    assert field.selected_provider() == "crossref"


def test_unknown_strategy_is_a_configuration_error():
    field = FieldValue(merge_strategy="not-a-strategy")

    with pytest.raises(FusionConfigurationError, match="Unknown fusion strategy"):
        field.add("crossref", "value")


def test_unknown_fields_are_rejected():
    with pytest.raises(ValueError, match="Unknown publication field.*year"):
        FusionEngine().merge(None, {"provider": "crossref", "year": 2024})
