from dataclasses import dataclass, field

from research_documentation.models.uml.element import UMLElement


@dataclass(slots=True)
class UMLClassifier(UMLElement):
    """
    Base class for every UML classifier.

    A classifier is any UML element that can be used as the
    type of an attribute, parameter or relationship.
    """

    package: str = ""

    is_abstract: bool = False

    keywords: list[str] = field(default_factory=list)
