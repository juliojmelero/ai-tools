from dataclasses import dataclass, field

from research_models.field_value import FieldValue
from research_engine.provider_priorities import (
    FIELD_RULES,
    merge_strategy,
    providers_for_field,
)


class UnknownPublicationFieldError(ValueError):
    """Raised when data targets a field outside the canonical model."""


@dataclass
class Publication:
    fields: dict[str, FieldValue] = field(default_factory=dict)

    def __post_init__(self):
        for field_name in FIELD_RULES:
            if field_name not in self.fields:
                self.fields[field_name] = FieldValue(
                    merge_strategy=merge_strategy(field_name)
                )
            self.fields[field_name].reselect(providers_for_field(field_name))

    def add(self, provider, field_name, value, quality=None):
        if field_name not in FIELD_RULES:
            raise UnknownPublicationFieldError(
                f"Unknown canonical publication field: {field_name!r}"
            )

        self.fields[field_name].add(
            provider=provider,
            value=value,
            quality=quality,
            provider_order=providers_for_field(field_name),
        )

    def get(self, field_name):
        if field_name not in self.fields:
            return None
        return self.fields[field_name].selected

    def contributors(self, field_name):
        if field_name not in self.fields:
            return []
        return self.fields[field_name].contributors()

    def selected_provider(self, field_name):
        if field_name not in self.fields:
            return None
        return self.fields[field_name].selected_provider()

    def to_dict(self):
        return {
            field: value.to_dict()
            for field, value in self.fields.items()
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        for field_name, field_data in data.items():
            if field_name not in FIELD_RULES:
                raise UnknownPublicationFieldError(
                    f"Unknown canonical publication field: {field_name!r}"
                )
            obj.fields[field_name] = FieldValue.from_dict(field_data)
            obj.fields[field_name].reselect(providers_for_field(field_name))
        return obj


def publications_response(provider, query, publications):
    return {
        "provider": provider,
        "query": query,
        "count": len(publications),
        "results": publications,
    }
