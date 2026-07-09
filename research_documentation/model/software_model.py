from dataclasses import dataclass, field

from research_documentation.model.graph.dependency_graph import DependencyGraph
from research_documentation.model.software_class import SoftwareClass
from research_documentation.model.software_package import SoftwarePackage
from research_documentation.model.software_relationship import SoftwareRelationship


@dataclass(slots=True)
class SoftwareModel:
    """
    Language-independent representation of a software project.
    """

    name: str

    packages: list[SoftwarePackage] = field(default_factory=list)

    classifiers: list[SoftwareClass] = field(default_factory=list)

    relationships: list[SoftwareRelationship] = field(default_factory=list)

    dependency_graph: DependencyGraph = field(default_factory=DependencyGraph)

    imports: dict[str, str] = field(default_factory=dict)

    module_imports: dict[str, dict[str, str]] = field(default_factory=dict)

    def add_class(self, software_class: SoftwareClass) -> None:
        existing = self.get_class(software_class.name)
        if existing is not None:
            index = self.classifiers.index(existing)
            self.classifiers[index] = software_class
            return

        self.classifiers.append(software_class)

    def get_class(self, name: str) -> SoftwareClass | None:
        for classifier in self.classifiers:
            if classifier.name == name:
                return classifier

        return None

    def add_package(self, package: SoftwarePackage) -> None:
        if self.get_package(package.name) is None:
            self.packages.append(package)

    def get_package(self, name: str) -> SoftwarePackage | None:
        for package in self.packages:
            if package.name == name:
                return package

        return None

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
    def classes(self) -> dict[str, SoftwareClass]:
        return {
            classifier.name: classifier
            for classifier in self.classifiers
        }

    def __len__(self):
        return len(self.classifiers)
