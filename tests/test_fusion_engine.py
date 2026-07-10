import itertools

import pytest

from research_engine.fusion_engine import FusionEngine
from research_engine.merge_strategies import FusionConfigurationError
from research_models.field_value import FieldValue
from research_models.provider_value import ProviderValue
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
        "current": True,
    }
    assert title_values[1] == {
        "provider": "openalex",
        "value": "A longer example title",
        "quality": None,
        "timestamp": second_timestamp,
        "current": True,
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


def _field_with_observations(strategy, observations):
    field = FieldValue(merge_strategy=strategy)
    for value, timestamp in observations:
        field.add("crossref", value, timestamp=timestamp)
    return field


def test_same_provider_same_value_twice_preserves_both_observations():
    field = _field_with_observations(
        "first_non_empty",
        [("Title", "2025-01-01T00:00:00Z"), ("Title", "2025-01-02T00:00:00Z")],
    )

    assert len(field.values) == 2
    assert [value.current for value in field.values] == [False, True]
    assert field.selected == "Title"


def test_same_provider_newer_scalar_replaces_current_observation():
    field = _field_with_observations(
        "first_non_empty",
        [("Old", "2025-01-01T00:00:00Z"), ("New", "2025-01-02T00:00:00Z")],
    )

    assert field.selected == "New"
    assert [value.value for value in field.current_values()] == ["New"]


def test_same_provider_older_update_arriving_later_stays_historical():
    field = _field_with_observations(
        "first_non_empty",
        [("New", "2025-01-02T00:00:00Z"), ("Old", "2025-01-01T00:00:00Z")],
    )

    assert field.selected == "New"
    assert [value.value for value in field.values] == ["Old", "New"]
    assert [value.current for value in field.values] == [False, True]


def test_same_provider_list_update_uses_only_latest_list():
    field = _field_with_observations(
        "union",
        [
            (["old", "shared"], "2025-01-01T00:00:00Z"),
            (["new", "shared"], "2025-01-02T00:00:00Z"),
        ],
    )

    assert field.selected == ["new", "shared"]
    assert len(field.values) == 2


def test_same_timestamp_uses_canonical_content_tie_breaker():
    timestamp = "2025-01-01T00:00:00Z"
    forward = _field_with_observations(
        "first_non_empty", [("Alpha", timestamp), ("Zulu", timestamp)]
    )
    reverse = _field_with_observations(
        "first_non_empty", [("Zulu", timestamp), ("Alpha", timestamp)]
    )

    assert forward.selected == reverse.selected == "Zulu"


def test_serialize_reload_and_merge_preserves_history_and_current_state():
    publication = Publication()
    publication.add(
        "crossref", "title", "First", timestamp="2025-01-01T00:00:00Z"
    )
    publication.add(
        "crossref", "title", "Second", timestamp="2025-01-02T00:00:00Z"
    )

    reloaded = Publication.from_dict(publication.to_dict())
    reloaded.add("crossref", "title", "Third", timestamp="2025-01-03T00:00:00Z")

    title = reloaded.fields["title"]
    assert [value.value for value in title.values] == ["First", "Second", "Third"]
    assert [value.current for value in title.values] == [False, False, True]
    assert title.selected == "Third"


def test_repeated_provider_selection_is_permutation_independent():
    observations = [
        ("Middle", "2025-01-02T00:00:00Z"),
        ("Newest", "2025-01-03T00:00:00Z"),
        ("Oldest", "2025-01-01T00:00:00Z"),
    ]

    results = {
        _field_with_observations("first_non_empty", permutation).selected
        for permutation in itertools.permutations(observations)
    }
    assert results == {"Newest"}


def test_empty_update_does_not_replace_current_observation():
    field = _field_with_observations(
        "first_non_empty", [("Title", "2025-01-01T00:00:00Z")]
    )
    field.add("crossref", "", timestamp="2025-01-02T00:00:00Z")

    assert field.selected == "Title"
    assert len(field.values) == 1


@pytest.mark.parametrize(
    "timestamps",
    [
        ("2025-01-01T00:00:00Z", "2025-01-01T00:00:00+00:00"),
        ("2025-01-01T00:00:00+00:00", "2025-01-01T00:00:00Z"),
    ],
)
def test_equivalent_timestamp_spellings_are_order_independent(timestamps):
    field = _field_with_observations(
        "first_non_empty", [("same", timestamp) for timestamp in timestamps]
    )

    assert [value.timestamp for value in field.values] == [
        "2025-01-01T00:00:00+00:00",
        "2025-01-01T00:00:00Z",
    ]
    assert [value.current for value in field.values] == [False, True]


def test_exact_duplicate_observations_have_one_deterministic_current():
    timestamp = "2025-01-01T00:00:00Z"
    def duplicates():
        return [
            ProviderValue("crossref", "same", timestamp),
            ProviderValue("crossref", "same", timestamp),
        ]

    forward_observations = duplicates()
    reverse_observations = duplicates()
    forward = FieldValue(values=forward_observations)
    reverse = FieldValue(values=list(reversed(reverse_observations)))
    forward.reselect()
    reverse.reselect()

    assert forward.to_dict() == reverse.to_dict()
    assert len(forward.values) == 2
    assert sum(value.current for value in forward.values) == 1
    assert [value.to_dict() for value in forward.values] == [
        {
            "provider": "crossref",
            "value": "same",
            "timestamp": timestamp,
            "quality": None,
            "current": False,
        },
        {
            "provider": "crossref",
            "value": "same",
            "timestamp": timestamp,
            "quality": None,
            "current": True,
        },
    ]


@pytest.mark.parametrize(
    "timestamps",
    [("not-a-date", "also-not-a-date"), ("also-not-a-date", "not-a-date")],
)
def test_malformed_timestamps_are_order_independent(timestamps):
    field = _field_with_observations(
        "first_non_empty",
        [(timestamp, timestamp) for timestamp in timestamps],
    )

    assert [value.timestamp for value in field.values] == [
        "also-not-a-date",
        "not-a-date",
    ]
    assert field.selected == "not-a-date"
