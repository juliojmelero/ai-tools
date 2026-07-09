from dataclasses import dataclass

from research_documentation.model.types.type_reference import TypeReference


@dataclass(slots=True)
class SoftwareParameter:
    """
    Represents one method parameter.
    """

    name: str

    type_name: str

    type_reference: TypeReference

    default_value: str | None = None
