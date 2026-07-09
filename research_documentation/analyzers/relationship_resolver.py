from research_documentation.model.software_model import SoftwareModel
from research_documentation.model.software_relationship import (
    SoftwareRelationship,
    SoftwareRelationshipType,
)


class RelationshipResolver:

    def resolve(
        self,
        model: SoftwareModel,
    ) -> SoftwareModel:

        self._inheritance(model)
        self._attributes(model)

        return model

    def _inheritance(self, model):

        for cls in model.classifiers:

            for base in cls.bases:

                parent = model.get_class(base)

                if parent is None:
                    continue

                self._add(
                    model,
                    SoftwareRelationship(
                        source=cls,
                        target=parent,
                        relationship_type=SoftwareRelationshipType.INHERITANCE,
                    ),
                )

    def _attributes(self, model):

        for cls in model.classifiers:

            for attribute in cls.attributes:

                if attribute.resolved_type is None:
                    continue

                self._add(
                    model,
                    SoftwareRelationship(
                        source=cls,
                        target=attribute.resolved_type,
                        relationship_type=SoftwareRelationshipType.COMPOSITION,
                        multiplicity=self._multiplicity(attribute.type_reference),
                        label=attribute.name,
                    ),
                )

    def _multiplicity(self, type_reference):

        if type_reference.is_collection():
            return "*"

        if type_reference.is_dictionary():
            return "*"

        if type_reference.is_optional:
            return "0..1"

        return "1"

    def _add(self, model, relation):

        for existing in model.relationships:

            if (
                existing.source is relation.source
                and existing.target is relation.target
                and existing.relationship_type == relation.relationship_type
                and existing.label == relation.label
            ):
                return

        model.add_relationship(relation)
