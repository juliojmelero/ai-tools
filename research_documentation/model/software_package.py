from dataclasses import dataclass, field

from research_documentation.model.software_class import SoftwareClass


@dataclass(slots=True)
class SoftwarePackage:
    """
    Language-independent representation of a software package.
    """

    name: str

    classifiers: list[SoftwareClass] = field(default_factory=list)

    def add_classifier(self, classifier: SoftwareClass) -> None:
        if classifier not in self.classifiers:
            self.classifiers.append(classifier)
