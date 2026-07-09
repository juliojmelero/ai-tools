from dataclasses import dataclass

from research_documentation.model.types.type_reference import TypeReference


@dataclass(slots=True)
class SoftwareAttribute:
    """
    Represents one software attribute.
    """

    name: str

    type_name: str

    type_reference: TypeReference

    resolved_type: object | None = None

    visibility: str = "private"

    documentation: str = ""

    @property
    def is_relationship(self) -> bool:
        return self.resolved_type is not None
