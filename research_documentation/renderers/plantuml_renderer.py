from research_documentation.models.uml.model import UMLModel
from research_documentation.models.uml.relationship import RelationshipType


class PlantUMLRenderer:
    """
    Renders UMLModel objects as PlantUML source text.
    """

    @property
    def name(self) -> str:
        return "PlantUML Renderer"

    def render(self, model: UMLModel) -> str:
        lines = [
            "@startuml",
            "skinparam classAttributeIconSize 0",
            "",
            f"title {model.name}",
            "",
        ]

        for classifier in model.classifiers:
            lines.extend(self._render_class(classifier))
            lines.append("")

        for relationship in model.relationships:
            lines.append(self._render_relationship(relationship))

        lines.append("")
        lines.append("@enduml")

        return "\n".join(lines)

    def _render_class(self, uml_class) -> list[str]:
        lines = [f"class {uml_class.name} {{"]

        for attribute in uml_class.attributes:
            lines.append(
                f"  {attribute.visibility.value} {attribute.name}: {attribute.type}"
            )

        for method in uml_class.methods:
            lines.append(f"  + {method}")

        lines.append("}")

        return lines

    def _render_relationship(self, relationship) -> str:
        arrow = self._arrow(relationship.relationship_type)

        source_mult = relationship.source_multiplicity
        target_mult = relationship.target_multiplicity

        label = f" : {relationship.label}" if relationship.label else ""

        return (
            f'{relationship.source.name} "{source_mult}" '
            f'{arrow} "{target_mult}" '
            f"{relationship.target.name}{label}"
        )

    def _arrow(self, relationship_type: RelationshipType) -> str:
        if relationship_type == RelationshipType.COMPOSITION:
            return "*--"

        if relationship_type == RelationshipType.AGGREGATION:
            return "o--"

        if relationship_type == RelationshipType.GENERALIZATION:
            return "--|>"

        if relationship_type == RelationshipType.REALIZATION:
            return "..|>"

        if relationship_type == RelationshipType.DEPENDENCY:
            return "..>"

        return "--"
