from dataclasses import dataclass, field

from research_documentation.model.software_parameter import SoftwareParameter
from research_documentation.model.types.type_reference import TypeReference


@dataclass(slots=True)
class SoftwareMethod:
    """
    Represents one software method.
    """

    name: str

    parameters: list[SoftwareParameter] = field(default_factory=list)

    return_type_name: str = "Any"

    return_type: TypeReference = field(
        default_factory=lambda: TypeReference("Any")
    )

    decorators: list[str] = field(default_factory=list)

    documentation: str = ""

    visibility: str = "public"

    @property
    def signature(self) -> str:

        params = ", ".join(
            f"{p.name}: {p.type_name}"
            for p in self.parameters
        )

        return f"{self.name}({params})"
