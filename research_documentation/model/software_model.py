from dataclasses import dataclass, field

from research_documentation.model.software_class import SoftwareClass
from research_documentation.model.software_package import SoftwarePackage
from research_documentation.model.software_relationship import SoftwareRelationship


@dataclass(slots=True)
class SoftwareModel:
    """
    Language-independent representation of a software project.
    """

    name: str

    classes: dict[str, SoftwareClass] = field(default_factory=dict)

    packages: dict[str, SoftwarePackage] = field(default_factory=dict)

    relationships: list[SoftwareRelationship] = field(default_factory=list)

    imports: dict[str, str] = field(default_factory=dict)

    module_imports: dict[str, dict[str, str]] = field(default_factory=dict)

    def add_class(self, software_class: SoftwareClass) -> None:
        self.classes[software_class.name] = software_class

        package_name = software_class.package_name or software_class.package
        if package_name in self.packages:
            self.packages[package_name].add_classifier(software_class)

    def get_class(self, name: str) -> SoftwareClass | None:
        return self.classes.get(name)

    def add_package(self, software_package: SoftwarePackage) -> None:
        self.packages.setdefault(software_package.name, software_package)

    def get_package(self, name: str) -> SoftwarePackage | None:
        return self.packages.get(name)

    def add_relationship(self, relationship: SoftwareRelationship) -> None:
        self.relationships.append(relationship)

    def add_import(self, alias: str, qualified_name: str, module: str | None = None) -> None:
        self.imports[alias] = qualified_name

        if module:
            self.module_imports.setdefault(module, {})
            self.module_imports[module][alias] = qualified_name

    def imports_for_module(self, module: str) -> dict[str, str]:
        return self.module_imports.get(module, {})

    @property
    def classifiers(self):
        return self.classes.values()

    def __len__(self):
        return len(self.classes)
