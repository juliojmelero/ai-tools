from research_documentation.model.graph.dependency_graph import DependencyGraph
from research_documentation.model.software_model import SoftwareModel


class DependencyAnalyzer:
    """
    Builds a dependency graph from software relationships.
    """

    def analyze(self, model: SoftwareModel) -> DependencyGraph:
        graph = DependencyGraph()

        for relationship in model.relationships:
            graph.add_dependency(
                source=relationship.source,
                target=relationship.target,
            )

        return graph
