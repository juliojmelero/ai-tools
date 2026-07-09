from dataclasses import dataclass, field

from research_documentation.models.uml.class_ import UMLClass
from research_documentation.models.uml.relationship import UMLRelationship


@dataclass(slots=True)
class UMLModel:
    """
    Root UML model.

    Contains every classifier and relationship of a software system.
    """

    name: str

    classes: dict[str, UMLClass] = field(default_factory=dict)

    relationships: list[UMLRelationship] = field(default_factory=list)

    def add_class(self, uml_class: UMLClass) -> None:
        self.classes[uml_class.name] = uml_class

    def get_class(self, name: str) -> UMLClass | None:
        return self.classes.get(name)

    def add_relationship(self, relationship: UMLRelationship) -> None:
        self.relationships.append(relationship)

    @property
    def classifiers(self):
        return self.classes.values()

    def __len__(self) -> int:
        return len(self.classes)
