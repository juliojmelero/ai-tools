from dataclasses import dataclass, field

from research_documentation.model.software_class import SoftwareClass


@dataclass(slots=True)
class DependencyEdge:
    """
    Directed dependency edge between two software classes.
    """

    source: SoftwareClass

    target: SoftwareClass


@dataclass(slots=True)
class DependencyGraph:
    """
    Directed dependency graph between software classes.
    """

    edges: list[DependencyEdge] = field(default_factory=list)

    def add_dependency(
        self,
        source: SoftwareClass,
        target: SoftwareClass,
    ) -> None:

        for edge in self.edges:
            if edge.source is source and edge.target is target:
                return

        self.edges.append(
            DependencyEdge(
                source=source,
                target=target,
            )
        )

    def dependencies_of(
        self,
        software_class: SoftwareClass,
    ) -> list[SoftwareClass]:

        dependencies = []

        for edge in self.edges:
            if edge.source is software_class:
                dependencies.append(edge.target)

        return dependencies

    @property
    def nodes(self) -> list[SoftwareClass]:
        nodes = []
        seen_ids = set()

        for edge in self.edges:
            for software_class in (edge.source, edge.target):
                software_class_id = id(software_class)

                if software_class_id in seen_ids:
                    continue

                seen_ids.add(software_class_id)
                nodes.append(software_class)

        return nodes
