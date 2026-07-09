import ast

from research_documentation.analyzers.types.type_parser import TypeParser
from research_documentation.model.software_attribute import SoftwareAttribute
from research_documentation.model.software_class import SoftwareClass


class AttributeExtractor:
    """
    Extracts class attributes from Python type annotations.
    """

    def __init__(self):
        self.type_parser = TypeParser()

    def extract(
        self,
        class_node: ast.ClassDef,
        software_class: SoftwareClass,
    ) -> None:

        for node in class_node.body:

            if not isinstance(node, ast.AnnAssign):
                continue

            if not isinstance(node.target, ast.Name):
                continue

            software_class.add_attribute(
                SoftwareAttribute(
                    name=node.target.id,
                    type_name=self._type_string(node.annotation),
                    type_reference=self.type_parser.parse(node.annotation),
                )
            )

    def _type_string(self, annotation) -> str:
        if hasattr(ast, "unparse"):
            return ast.unparse(annotation)

        return "Any"
