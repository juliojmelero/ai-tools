from abc import ABC, abstractmethod


CURRENT_SCHEMA_VERSION = 1


class MissingPublicationSchemaVersionError(ValueError):
    """Raised when canonical publication data has no schema version."""


class UnsupportedPublicationSchemaVersionError(ValueError):
    """Raised when canonical publication data uses an unknown schema version."""


class PublicationSerializer(ABC):
    """Interface implemented by version-specific publication serializers."""

    schema_version: int

    @abstractmethod
    def serialize(self, publication):
        """Return the canonical dictionary for a publication."""

    def upgrade(self, data):
        raise NotImplementedError

    def downgrade(self, data):
        raise NotImplementedError


class PublicationDeserializer(ABC):
    """Interface implemented by version-specific publication deserializers."""

    schema_version: int

    @abstractmethod
    def deserialize(self, data, publication_cls):
        """Build a publication from a canonical dictionary."""

    def upgrade(self, data):
        raise NotImplementedError

    def downgrade(self, data):
        raise NotImplementedError


def _serializers():
    from research_models.serialization.publication_v1 import PublicationV1Serializer

    return {PublicationV1Serializer.schema_version: PublicationV1Serializer()}


def _deserializers():
    from research_models.serialization.publication_v1 import PublicationV1Deserializer

    return {PublicationV1Deserializer.schema_version: PublicationV1Deserializer()}


def serialize_publication(publication, version=CURRENT_SCHEMA_VERSION):
    try:
        serializer = _serializers()[version]
    except KeyError as exc:
        raise UnsupportedPublicationSchemaVersionError(
            f"Unsupported publication schema version: {version!r}"
        ) from exc
    return serializer.serialize(publication)


def deserialize_publication(data, publication_cls):
    if "_schema_version" not in data:
        raise MissingPublicationSchemaVersionError(
            "Canonical publication data requires '_schema_version'"
        )

    version = data["_schema_version"]
    try:
        deserializer = _deserializers()[version]
    except (KeyError, TypeError) as exc:
        raise UnsupportedPublicationSchemaVersionError(
            f"Unsupported publication schema version: {version!r}"
        ) from exc
    return deserializer.deserialize(data, publication_cls)


def upgrade(data):
    raise NotImplementedError


def downgrade(data):
    raise NotImplementedError


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MissingPublicationSchemaVersionError",
    "PublicationDeserializer",
    "PublicationSerializer",
    "UnsupportedPublicationSchemaVersionError",
    "deserialize_publication",
    "downgrade",
    "serialize_publication",
    "upgrade",
]
