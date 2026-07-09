from dataclasses import dataclass
from enum import Enum

from research_documentation.models.uml.element import UMLElement


class Visibility(Enum):
    PUBLIC = "+"
    PRIVATE = "-"
    PROTECTED = "#"
    PACKAGE = "~"


@dataclass(slots=True)
class UMLAttribute(UMLElement):
    """
    UML class attribute.
    """

    type: str = "Any"

    visibility: Visibility = Visibility.PRIVATE

    default: str | None = None

    is_static: bool = False

    is_final: bool = False

    multiplicity: str = "1"
