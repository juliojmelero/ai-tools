from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_documentation.model.software_class import SoftwareClass


class SoftwareRelationshipType(Enum):
    INHERITANCE = "inheritance"
    COMPOSITION = "composition"
    AGGREGATION = "aggregation"
    ASSOCIATION = "association"
    DEPENDENCY = "dependency"


@dataclass(slots=True)
class SoftwareRelationship:
    """
    Relationship between two SoftwareClass objects.
    """

    source: "SoftwareClass"

    target: "SoftwareClass"

    relationship_type: SoftwareRelationshipType

    multiplicity: str = "1"

    label: str = ""
