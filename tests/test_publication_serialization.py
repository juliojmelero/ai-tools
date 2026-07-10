import json

import pytest

from research_engine.fusion_engine import FusionEngine
from research_models.publication import Publication
from research_models.serialization import (
    MissingPublicationSchemaVersionError,
    PublicationDeserializer,
    PublicationSerializer,
    UnsupportedPublicationSchemaVersionError,
    downgrade,
    upgrade,
)
from research_models.serialization.publication_v1 import (
    PublicationV1Deserializer,
    PublicationV1Serializer,
)


def _publication_with_history():
    publication = Publication()
    publication.add(
        "crossref",
        "title",
        "Earlier title",
        quality=0.8,
        timestamp="2025-01-01T00:00:00Z",
    )
    publication.add(
        "crossref",
        "title",
        "Current title",
        quality=0.95,
        timestamp="2025-01-02T00:00:00Z",
    )
    return publication


def test_v1_round_trip_preserves_complete_canonical_record():
    serialized = _publication_with_history().to_dict()

    reloaded = Publication.from_dict(serialized)

    assert reloaded.to_dict() == serialized
    observations = reloaded.to_dict()["_record"]["title"]["values"]
    assert [value["quality"] for value in observations] == [0.8, 0.95]
    assert [value["timestamp"] for value in observations] == [
        "2025-01-01T00:00:00Z",
        "2025-01-02T00:00:00Z",
    ]
    assert [value["current"] for value in observations] == [False, True]


def test_missing_schema_version_is_rejected():
    with pytest.raises(MissingPublicationSchemaVersionError):
        Publication.from_dict({"_record": {}})


def test_unknown_future_schema_version_is_rejected():
    with pytest.raises(UnsupportedPublicationSchemaVersionError):
        Publication.from_dict({"_schema_version": 2, "_record": {}})


def test_schema_version_survives_serialization():
    serialized = Publication().to_dict()

    assert serialized["_schema_version"] == 1
    assert Publication.from_dict(serialized).to_dict()["_schema_version"] == 1


def test_existing_cached_canonical_record_remains_readable():
    engine = FusionEngine()
    cached = engine.merge(
        None,
        {"provider": "crossref", "title": "Cached title", "quality": 0.9},
    )
    legacy_cached = dict(cached)
    legacy_cached.pop("_schema_version")

    reloaded = engine.merge(
        legacy_cached,
        {"provider": "openalex", "abstract": "New abstract"},
    )

    assert cached["_schema_version"] == 1
    assert reloaded["title"] == "Cached title"
    assert reloaded["abstract"] == "New abstract"
    assert reloaded["_record"]["title"] == cached["_record"]["title"]


def test_serializer_produces_byte_identical_output_for_identical_input():
    publication = _publication_with_history()

    first = json.dumps(publication.to_dict(), separators=(",", ":"))
    second = json.dumps(publication.to_dict(), separators=(",", ":"))

    assert first.encode() == second.encode()


def test_publication_from_dict_dispatches_to_v1(monkeypatch):
    calls = []
    original = PublicationV1Deserializer.deserialize

    def recording_deserialize(self, data, publication_cls):
        calls.append(data["_schema_version"])
        return original(self, data, publication_cls)

    monkeypatch.setattr(
        PublicationV1Deserializer, "deserialize", recording_deserialize
    )

    Publication.from_dict(Publication().to_dict())

    assert calls == [1]


def test_versioned_serializers_implement_public_interfaces():
    assert isinstance(PublicationV1Serializer(), PublicationSerializer)
    assert isinstance(PublicationV1Deserializer(), PublicationDeserializer)


@pytest.mark.parametrize("migration", [upgrade, downgrade])
def test_migration_hooks_are_explicit(migration):
    with pytest.raises(NotImplementedError):
        migration({"_schema_version": 1, "_record": {}})
