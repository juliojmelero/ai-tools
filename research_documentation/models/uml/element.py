from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(slots=True)
class UMLElement:
    """
    Base class for every UML element.
    """

    name: str

    id: str = field(default_factory=lambda: str(uuid4()))

    documentation: str = ""

    stereotype: str | None = None

    def __str__(self) -> str:
        return self.name
