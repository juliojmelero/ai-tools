from research_documentation.analyzers.analysis_context import AnalysisContext
from research_documentation.analyzers.analysis_result import AnalysisResult
from research_documentation.analyzers.base_analyzer import BaseAnalyzer
from research_documentation.analyzers.dependency.dependency_analyzer import (
    DependencyAnalyzer,
)
from research_documentation.analyzers.relationship_resolver import RelationshipResolver
from research_documentation.analyzers.type_resolver import TypeResolver
from research_documentation.model.software_model import SoftwareModel


class TypeResolverAnalyzer(BaseAnalyzer):
    """
    Pipeline wrapper for TypeResolver.
    """

    name = "type_resolver"

    def __init__(self, resolver: TypeResolver | None = None) -> None:
        self.resolver = resolver or TypeResolver()

    def analyze(
        self,
        model: SoftwareModel,
        context: AnalysisContext,
    ) -> AnalysisResult:
        self.resolver.resolve(model)
        return AnalysisResult.ok(self.name)


class RelationshipResolverAnalyzer(BaseAnalyzer):
    """
    Pipeline wrapper for RelationshipResolver.
    """

    name = "relationship_resolver"
    dependencies = ["type_resolver"]

    def __init__(self, resolver: RelationshipResolver | None = None) -> None:
        self.resolver = resolver or RelationshipResolver()

    def analyze(
        self,
        model: SoftwareModel,
        context: AnalysisContext,
    ) -> AnalysisResult:
        self.resolver.resolve(model)
        return AnalysisResult.ok(self.name)


class DependencyGraphAnalyzer(BaseAnalyzer):
    """
    Pipeline wrapper for DependencyAnalyzer.
    """

    name = "dependency_graph"
    dependencies = ["relationship_resolver"]

    def __init__(self, analyzer: DependencyAnalyzer | None = None) -> None:
        self.analyzer = analyzer or DependencyAnalyzer()

    def analyze(
        self,
        model: SoftwareModel,
        context: AnalysisContext,
    ) -> AnalysisResult:
        model.dependency_graph = self.analyzer.analyze(model)
        return AnalysisResult.ok(self.name)
