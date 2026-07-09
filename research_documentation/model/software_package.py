from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_documentation.model.software_class import SoftwareClass


@dataclass(slots=True)
class SoftwarePackage:
    """
    Language-independent representation of a software package or namespace.
    """

    name: str

    parent: SoftwarePackage | None = None

    subpackages: list[SoftwarePackage] = field(default_factory=list)

    classifiers: list[SoftwareClass] = field(default_factory=list)

    def add_subpackage(self, package: SoftwarePackage) -> None:
        if package.parent is not None and package.parent is not self:
            raise ValueError(
                f"Package {package.name!r} already belongs to another parent"
            )

        if package in self.subpackages:
            return

        package.parent = self
        self.subpackages.append(package)

    def add_classifier(self, classifier: SoftwareClass) -> None:
        if classifier.package_name and classifier.package_name != self.name:
            raise ValueError(
                f"Classifier {classifier.name!r} already belongs to another package"
            )

        if classifier in self.classifiers:
            return

        classifier.package_name = self.name
        self.classifiers.append(classifier)
