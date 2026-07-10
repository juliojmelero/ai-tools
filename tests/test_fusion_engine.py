import itertools
from dataclasses import FrozenInstanceError

import pytest

from research_engine.fusion_engine import FusionEngine
from research_engine.merge_strategies import FusionConfigurationError, select
from research_models.field_value import FieldValue
from research_models.provider_value import (
    InvalidProviderIdentifierError,
    InvalidProviderValueQualityError,
    InvalidProviderValueTimestampError,
    ProviderValue,
)
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
    serialized.update(publication.to_dict())

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


@pytest.mark.parametrize("quality", [0.0, 1.0])
def test_quality_boundary_values_are_valid(quality):
    value = ProviderValue.create("crossref", "title", quality=quality)

    assert value.quality == quality


@pytest.mark.parametrize(
    "quality", [float("nan"), float("inf"), float("-inf"), True, False, -0.1, 1.1]
)
def test_invalid_quality_is_a_domain_error(quality):
    with pytest.raises(
        InvalidProviderValueQualityError,
        match="quality must be None or a finite numeric value between 0.0 and 1.0",
    ):
        ProviderValue.create("crossref", "title", quality=quality)


def test_provider_value_quality_cannot_be_mutated_after_construction():
    value = ProviderValue.create("crossref", "title", quality=0.5)

    with pytest.raises(FrozenInstanceError):
        value.quality = float("nan")


def _forge_invalid_quality(value):
    object.__setattr__(value, "quality", float("nan"))
    return value


def test_field_value_rejects_invalid_prebuilt_provider_value():
    invalid = _forge_invalid_quality(
        ProviderValue.create("crossref", "title", quality=0.5)
    )

    with pytest.raises(InvalidProviderValueQualityError):
        FieldValue(values=[invalid])


def test_serialization_rejects_forged_invalid_observation():
    field = FieldValue()
    field.add("crossref", "title", quality=0.5)
    _forge_invalid_quality(field.values[0])

    with pytest.raises(InvalidProviderValueQualityError):
        field.to_dict()


@pytest.mark.parametrize("strategy", ["first_non_empty", "overwrite"])
def test_provider_priority_precedes_quality(strategy):
    field = FieldValue(merge_strategy=strategy)
    provider_order = ["crossref", "openalex"]
    field.add(
        "openalex", "high quality", quality=1.0, provider_order=provider_order
    )
    field.add(
        "crossref", "low quality", quality=0.0, provider_order=provider_order
    )

    assert field.selected == "low quality"


@pytest.mark.parametrize("strategy", ["first_non_empty", "overwrite"])
def test_equal_provider_priority_prefers_numeric_and_higher_quality(strategy):
    values = [
        ProviderValue.create("zeta", "none", quality=None),
        ProviderValue.create("alpha", "lower", quality=0.2),
        ProviderValue.create("omega", "higher", quality=0.8),
    ]

    selected, provider = select(strategy, values, [])

    assert (selected, provider) == ("higher", "omega")


def test_equal_longest_values_use_quality_after_provider_priority():
    values = [
        ProviderValue.create("alpha", "alpha", quality=None),
        ProviderValue.create("bravo", "bravo", quality=0.0),
        ProviderValue.create("delta", "delta", quality=1.0),
    ]

    assert select("longest", values, [])[0] == "delta"


def test_equal_maximum_values_use_quality_after_provider_priority():
    values = [
        ProviderValue.create("alpha", 10, quality=0.2),
        ProviderValue.create("omega", 10, quality=0.9),
    ]

    assert select("maximum", values, []) == (10, "omega")


def test_quality_aware_selection_is_permutation_independent():
    observations = [
        ("alpha", "alpha", 0.1),
        ("bravo", "bravo", None),
        ("delta", "delta", 0.9),
    ]
    results = set()
    for permutation in itertools.permutations(observations):
        field = FieldValue(merge_strategy="first_non_empty")
        for provider, value, quality in permutation:
            field.add(provider, value, quality=quality)
        results.add(field.selected)

    assert results == {"delta"}


def test_serialization_reload_preserves_quality_aware_selection_and_history():
    field = FieldValue(merge_strategy="overwrite")
    field.values = [
        ProviderValue.create("alpha", "none", quality=None),
        ProviderValue.create("omega", "best", quality=1.0),
    ]
    field.reselect([])

    reloaded = FieldValue.from_dict(field.to_dict())
    reloaded.reselect([])

    assert reloaded.selected == "best"
    assert [value.quality for value in reloaded.values] == [None, 1.0]


def test_union_quality_does_not_reorder_or_discard_duplicate_provenance():
    field = FieldValue(merge_strategy="union")
    provider_order = ["crossref", "openalex"]
    field.add(
        "openalex",
        ["shared", "openalex"],
        quality=1.0,
        provider_order=provider_order,
    )
    field.add(
        "crossref",
        ["crossref", "shared"],
        quality=0.0,
        provider_order=provider_order,
    )

    assert field.selected == ["crossref", "shared", "openalex"]
    assert field.contributors() == ["crossref", "openalex"]
    assert len(field.values) == 2


def test_unknown_strategy_is_a_configuration_error():
    field = FieldValue(merge_strategy="not-a-strategy")

    with pytest.raises(FusionConfigurationError, match="Unknown fusion strategy"):
        field.add("crossref", "value")


def test_unknown_provider_metadata_is_ignored():
    merged = FusionEngine().merge(
        None,
        {"provider": "crossref", "title": "Title", "source_score": 99},
    )

    assert "source_score" not in merged
    assert merged["title"] == "Title"


def test_flat_provider_quality_is_propagated_to_every_field():
    merged = FusionEngine().merge(
        None,
        {"provider": "crossref", "quality": 0.87, "title": "Title", "doi": "doi"},
    )

    assert merged["_record"]["title"]["values"][0]["quality"] == 0.87
    assert merged["_record"]["doi"]["values"][0]["quality"] == 0.87


def test_flat_provider_without_quality_preserves_none():
    merged = FusionEngine().merge(None, {"provider": "crossref", "title": "Title"})

    assert merged["_record"]["title"]["values"][0]["quality"] is None


@pytest.mark.parametrize("provider", [None, "", "   "])
def test_flat_record_requires_valid_provider(provider):
    with pytest.raises(InvalidProviderIdentifierError):
        FusionEngine().merge(None, {"provider": provider, "title": "Title"})


@pytest.mark.parametrize("provider", [None, "", "   "])
def test_direct_provider_value_rejects_invalid_provider(provider):
    with pytest.raises(InvalidProviderIdentifierError):
        ProviderValue(provider=provider, value="Title")


def test_provider_identifier_is_trimmed_without_changing_case():
    value = ProviderValue(provider="  CrossRef  ", value="Title")

    assert value.provider == "CrossRef"


def test_flat_provider_timestamp_is_propagated():
    timestamp = "2026-01-02T03:04:05Z"
    merged = FusionEngine().merge(
        None,
        {"provider": "crossref", "timestamp": timestamp, "title": "Title"},
    )

    assert merged["_record"]["title"]["values"][0]["timestamp"] == timestamp


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-01-02T03:04:05Z", "2026-01-02T03:04:05Z"),
        ("2026-01-02T04:04:05+01:00", "2026-01-02T03:04:05Z"),
        ("2026-01-02T03:04:05", "2026-01-02T03:04:05Z"),
    ],
)
def test_provider_value_normalizes_valid_timestamps_to_utc(timestamp, expected):
    value = ProviderValue(provider="crossref", value="Title", timestamp=timestamp)

    assert value.timestamp == expected


def test_provider_value_rejects_malformed_timestamp():
    with pytest.raises(InvalidProviderValueTimestampError):
        ProviderValue(provider="crossref", value="Title", timestamp="not-a-date")


def test_empty_timestamp_generates_canonical_utc_timestamp():
    value = ProviderValue(provider="crossref", value="Title", timestamp="  ")

    assert value.timestamp.endswith("Z")
    assert "+00:00" not in value.timestamp


def test_serialization_reload_preserves_canonical_utc_timestamp():
    value = ProviderValue(
        provider="crossref",
        value="Title",
        timestamp="2026-01-02T04:04:05+01:00",
    )

    reloaded = ProviderValue.from_dict(value.to_dict())

    assert reloaded.timestamp == value.timestamp == "2026-01-02T03:04:05Z"


def test_flat_provider_without_timestamp_uses_generated_default():
    merged = FusionEngine().merge(None, {"provider": "crossref", "title": "Title"})

    timestamp = merged["_record"]["title"]["values"][0]["timestamp"]
    assert timestamp.endswith("Z")


def test_flat_provider_quality_and_timestamp_are_propagated_together():
    timestamp = "2026-01-02T03:04:05Z"
    merged = FusionEngine().merge(
        None,
        {
            "provider": "crossref",
            "quality": 0.75,
            "timestamp": timestamp,
            "title": "Title",
        },
    )

    observation = merged["_record"]["title"]["values"][0]
    assert (observation["quality"], observation["timestamp"]) == (0.75, timestamp)


def test_several_flat_providers_preserve_their_distinct_qualities():
    merged = _fuse([
        {"provider": "alpha", "quality": 0.2, "title": "Alpha"},
        {"provider": "omega", "quality": 0.9, "title": "Omega"},
    ])

    assert {
        value["provider"]: value["quality"]
        for value in merged["_record"]["title"]["values"]
    } == {"alpha": 0.2, "omega": 0.9}


def test_flat_quality_survives_serialization_reload_and_merge():
    engine = FusionEngine()
    merged = engine.merge(
        None, {"provider": "alpha", "quality": 0.4, "title": "Alpha"}
    )
    reloaded = engine.merge(
        merged, {"provider": "omega", "quality": 0.8, "title": "Omega"}
    )

    assert [
        value["quality"] for value in reloaded["_record"]["title"]["values"]
    ] == [0.4, 0.8]


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
        "2025-01-01T00:00:00Z",
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
