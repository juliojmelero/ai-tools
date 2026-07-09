from dataclasses import dataclass, field

from research_documentation.model.software_class import SoftwareClass


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    source: SoftwareClass
    target: SoftwareClass


@dataclass(slots=True)
class DependencyGraph:
    dependencies: list[DependencyEdge] = field(default_factory=list)

    def add_dependency(
        self,
        source: SoftwareClass,
        target: SoftwareClass,
    ) -> None:
        self.dependencies.append(
            DependencyEdge(
                source=source,
                target=target,
            )
        )

    def dependencies_of(
        self,
        software_class: SoftwareClass,
    ) -> list[DependencyEdge]:
        return [
            dependency
            for dependency in self.dependencies
            if dependency.source == software_class
        ]

    @property
    def nodes(self) -> list[SoftwareClass]:
        nodes = []

        for dependency in self.dependencies:
            if dependency.source not in nodes:
                nodes.append(dependency.source)

            if dependency.target not in nodes:
                nodes.append(dependency.target)

        return nodes
