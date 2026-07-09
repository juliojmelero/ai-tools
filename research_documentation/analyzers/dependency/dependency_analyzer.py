from research_documentation.model.graph.dependency_graph import (
    DependencyGraph,
)

from research_documentation.model.software_model import SoftwareModel


class DependencyAnalyzer:
    """
    Builds a dependency graph from a SoftwareModel.
    """

    def analyze(
        self,
        model: SoftwareModel,
    ) -> DependencyGraph:

        graph = DependencyGraph()

        for relation in model.relationships:

            graph.add_dependency(
                relation.source,
                relation.target,
            )

        return graph
