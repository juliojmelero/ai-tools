from dataclasses import dataclass
from enum import Enum

from research_documentation.models.uml.classifier import UMLClassifier


class RelationshipType(Enum):
    ASSOCIATION = "association"
    AGGREGATION = "aggregation"
    COMPOSITION = "composition"
    GENERALIZATION = "generalization"
    REALIZATION = "realization"
    DEPENDENCY = "dependency"


@dataclass(slots=True)
class UMLRelationship:
    """
    Relationship between two UML classifiers.
    """

    source: UMLClassifier
    target: UMLClassifier

    relationship_type: RelationshipType

    source_multiplicity: str = "1"
    target_multiplicity: str = "1"

    source_role: str = ""
    target_role: str = ""

    label: str = ""

    bidirectional: bool = False
