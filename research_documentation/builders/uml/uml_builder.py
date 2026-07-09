from research_documentation.model.software_model import SoftwareModel
from research_documentation.model.software_relationship import SoftwareRelationshipType

from research_documentation.models.uml.attribute import UMLAttribute
from research_documentation.models.uml.class_ import UMLClass
from research_documentation.models.uml.model import UMLModel
from research_documentation.models.uml.relationship import UMLRelationship, RelationshipType


class UMLBuilder:
    """
    Builds a UMLModel from a SoftwareModel.
    """

    def build(self, software_model: SoftwareModel) -> UMLModel:
        uml_model = UMLModel(software_model.name)

        class_map = {}

        for software_class in software_model.classifiers:
            uml_class = UMLClass(software_class.name)

            for attribute in software_class.attributes:
                uml_class.add_attribute(
                    UMLAttribute(
                        name=attribute.name,
                        type=attribute.type_name,
                    )
                )

            for method in software_class.methods:
                uml_class.methods.append(self._method_signature(method))

            uml_model.add_class(uml_class)
            class_map[software_class.name] = uml_class

        for relation in software_model.relationships:
            source = class_map.get(relation.source.name)
            target = class_map.get(relation.target.name)

            if source is None or target is None:
                continue

            uml_model.add_relationship(
                UMLRelationship(
                    source=source,
                    target=target,
                    relationship_type=self._relationship_type(
                        relation.relationship_type
                    ),
                    target_multiplicity=relation.multiplicity,
                    label=relation.label,
                )
            )

        return uml_model

    def _relationship_type(self, relation_type: SoftwareRelationshipType) -> RelationshipType:
        mapping = {
            SoftwareRelationshipType.INHERITANCE: RelationshipType.GENERALIZATION,
            SoftwareRelationshipType.COMPOSITION: RelationshipType.COMPOSITION,
            SoftwareRelationshipType.AGGREGATION: RelationshipType.AGGREGATION,
            SoftwareRelationshipType.ASSOCIATION: RelationshipType.ASSOCIATION,
            SoftwareRelationshipType.DEPENDENCY: RelationshipType.DEPENDENCY,
        }

        return mapping[relation_type]

    def _method_signature(self, method) -> str:
        params = ", ".join(
            f"{p.name}: {p.type_name}"
            for p in method.parameters
        )

        return f"{method.name}({params}) -> {method.return_type_name}"
