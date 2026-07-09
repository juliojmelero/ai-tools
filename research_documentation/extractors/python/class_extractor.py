import ast
from pathlib import Path

from research_documentation.extractors.python.attribute_extractor import AttributeExtractor
from research_documentation.extractors.python.method_extractor import MethodExtractor

from research_documentation.model.software_class import SoftwareClass
from research_documentation.model.software_model import SoftwareModel


class ClassExtractor:

    def __init__(self):

        self.attribute_extractor = AttributeExtractor()
        self.method_extractor = MethodExtractor()

    def extract(
        self,
        tree: ast.Module,
        file: Path,
        model: SoftwareModel,
    ) -> None:

        module = file.stem

        for node in tree.body:

            if not isinstance(node, ast.ClassDef):
                continue

            software_class = SoftwareClass(
                name=node.name,
                module=module,
            )

            software_class.bases = [
                self._base_name(base)
                for base in node.bases
                if self._base_name(base)
            ]

            if ast.get_docstring(node):
                software_class.documentation = ast.get_docstring(node)

            self.attribute_extractor.extract(
                node,
                software_class,
            )

            self.method_extractor.extract(
                node,
                software_class,
            )

            model.add_class(
                software_class
            )

    def _base_name(self, base):

        if isinstance(base, ast.Name):
            return base.id

        if isinstance(base, ast.Attribute):
            return base.attr

        if isinstance(base, ast.Subscript):
            return self._base_name(base.value)

        return None
