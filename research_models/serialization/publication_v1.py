from research_engine.provider_priorities import FIELD_RULES, providers_for_field
from research_models.field_value import FieldValue
from research_models.serialization import (
    PublicationDeserializer,
    PublicationSerializer,
)


class PublicationV1Serializer(PublicationSerializer):
    schema_version = 1

    def serialize(self, publication):
        return {
            "_schema_version": self.schema_version,
            "_record": {
                field_name: field_value.to_dict()
                for field_name, field_value in publication.fields.items()
            },
        }


class PublicationV1Deserializer(PublicationDeserializer):
    schema_version = 1

    def deserialize(self, data, publication_cls):
        publication = publication_cls()
        for field_name, field_data in data["_record"].items():
            if field_name not in FIELD_RULES:
                # Import here to keep Publication's dependency on serializers
                # one-way during module initialization.
                from research_models.publication import UnknownPublicationFieldError

                raise UnknownPublicationFieldError(
                    f"Unknown canonical publication field: {field_name!r}"
                )
            publication.fields[field_name] = FieldValue.from_dict(field_data)
            publication.fields[field_name].reselect(providers_for_field(field_name))
        return publication
