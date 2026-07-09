from dataclasses import dataclass, field

from research_documentation.models.uml.attribute import UMLAttribute
from research_documentation.models.uml.classifier import UMLClassifier


@dataclass(slots=True)
class UMLClass(UMLClassifier):
    """
    UML class.
    """

    attributes: list[UMLAttribute] = field(default_factory=list)

    methods: list = field(default_factory=list)

    parents: list[str] = field(default_factory=list)

    interfaces: list[str] = field(default_factory=list)

    notes: list[str] = field(default_factory=list)

    def add_attribute(self, attribute: UMLAttribute) -> None:
        self.attributes.append(attribute)
