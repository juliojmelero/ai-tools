import ast
from pathlib import Path

from research_documentation.models.uml.attribute import UMLAttribute
from research_documentation.models.uml.class_ import UMLClass
from research_documentation.models.uml.model import UMLModel
from research_documentation.models.uml.relationship import (
    UMLRelationship,
    RelationshipType,
)


class PythonModelBuilder:
    """
    Builds a UMLModel from Python source code using ast.

    Detects:
    - classes
    - inheritance
    - methods
    - self attributes
    """

    def build_package(
        self,
        package_path: str | Path,
        model_name: str | None = None,
    ) -> UMLModel:
        package_path = Path(package_path)

        if not package_path.exists():
            raise FileNotFoundError(package_path)

        model = UMLModel(model_name or package_path.name)
        class_bases: dict[str, list[str]] = {}

        for file in package_path.rglob("*.py"):
            if file.name == "__init__.py":
                continue

            self._parse_file(
                file=file,
                model=model,
                class_bases=class_bases,
            )

        self._add_inheritance_relationships(
            model=model,
            class_bases=class_bases,
        )

        return model

    def _parse_file(
        self,
        file: Path,
        model: UMLModel,
        class_bases: dict[str, list[str]],
    ) -> None:
        tree = ast.parse(file.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                uml_class = UMLClass(node.name)

                self._add_methods(node, uml_class)
                self._add_self_attributes(node, uml_class)

                model.add_class(uml_class)

                class_bases[node.name] = [
                    self._base_name(base)
                    for base in node.bases
                    if self._base_name(base)
                ]

    def _add_methods(self, node: ast.ClassDef, uml_class: UMLClass) -> None:
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                uml_class.methods.append(f"{item.name}()")

    def _add_self_attributes(self, node: ast.ClassDef, uml_class: UMLClass) -> None:
        names = set()

        for item in ast.walk(node):
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    name = self._self_attribute_name(target)
                    if name:
                        names.add(name)

            if isinstance(item, ast.AnnAssign):
                name = self._self_attribute_name(item.target)
                if name:
                    names.add(name)

        for name in sorted(names):
            uml_class.add_attribute(
                UMLAttribute(
                    name=name,
                    type="Any",
                )
            )

    def _self_attribute_name(self, target) -> str | None:
        if not isinstance(target, ast.Attribute):
            return None

        if not isinstance(target.value, ast.Name):
            return None

        if target.value.id != "self":
            return None

        return target.attr

    def _base_name(self, base) -> str | None:
        if isinstance(base, ast.Name):
            return base.id

        if isinstance(base, ast.Attribute):
            return base.attr

        if isinstance(base, ast.Subscript):
            return self._base_name(base.value)

        return None

    def _add_inheritance_relationships(
        self,
        model: UMLModel,
        class_bases: dict[str, list[str]],
    ) -> None:
        for class_name, bases in class_bases.items():
            child = model.get_class(class_name)

            if child is None:
                continue

            for base_name in bases:
                parent = model.get_class(base_name)

                if parent is None:
                    parent = UMLClass(base_name)
                    model.add_class(parent)

                model.add_relationship(
                    UMLRelationship(
                        source=child,
                        target=parent,
                        relationship_type=RelationshipType.GENERALIZATION,
                    )
                )
