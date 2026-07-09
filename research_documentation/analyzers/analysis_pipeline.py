from enum import Enum

from research_documentation.analyzers.analysis_context import AnalysisContext
from research_documentation.analyzers.analysis_result import AnalysisResult
from research_documentation.analyzers.base_analyzer import BaseAnalyzer
from research_documentation.model.software_model import SoftwareModel


class AnalysisErrorPolicy(Enum):
    FAIL_FAST = "fail_fast"
    COLLECT_AND_CONTINUE = "collect_and_continue"
    CONTINUE_OPTIONAL_ONLY = "continue_optional_only"


class AnalysisPipelineError(RuntimeError):
    """
    Raised when the analysis pipeline cannot complete successfully.
    """

    def __init__(self, context: AnalysisContext):
        self.context = context
        messages = [
            diagnostic.message
            for diagnostic in context.diagnostics
            if diagnostic.severity == "error"
        ]
        super().__init__("; ".join(messages) or "Analysis pipeline failed")


class AnalysisPipeline:
    """
    Orchestrates SoftwareModel analyzers after extraction.
    """

    def __init__(
        self,
        analyzers: list[BaseAnalyzer] | None = None,
        error_policy: AnalysisErrorPolicy = AnalysisErrorPolicy.CONTINUE_OPTIONAL_ONLY,
    ) -> None:
        self.analyzers = analyzers or []
        self.error_policy = error_policy
        self.last_context: AnalysisContext | None = None

    def register(self, analyzer: BaseAnalyzer) -> None:
        self.analyzers.append(analyzer)

    def run(
        self,
        model: SoftwareModel,
        context: AnalysisContext | None = None,
    ) -> SoftwareModel:
        context = context or AnalysisContext()
        self.last_context = context

        for analyzer in self._ordered_analyzers():
            result = self._execute_analyzer(analyzer, model, context)
            context.record(result)

            if result.success:
                continue

            if self._should_stop(analyzer):
                raise AnalysisPipelineError(context)

        return model

    def _execute_analyzer(
        self,
        analyzer: BaseAnalyzer,
        model: SoftwareModel,
        context: AnalysisContext,
    ) -> AnalysisResult:
        try:
            return analyzer.analyze(model, context)
        except Exception as exc:
            return AnalysisResult.failed(
                analyzer_name=analyzer.name,
                message=f"{analyzer.name} failed: {exc}",
                exception=exc,
            )

    def _ordered_analyzers(self) -> list[BaseAnalyzer]:
        by_name = {analyzer.name: analyzer for analyzer in self.analyzers}
        ordered: list[BaseAnalyzer] = []
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(analyzer: BaseAnalyzer) -> None:
            if analyzer.name in permanent:
                return

            if analyzer.name in temporary:
                raise ValueError(f"Cyclic analyzer dependency: {analyzer.name}")

            temporary.add(analyzer.name)

            for dependency_name in analyzer.dependencies:
                dependency = by_name.get(dependency_name)
                if dependency is not None:
                    visit(dependency)

            temporary.remove(analyzer.name)
            permanent.add(analyzer.name)
            ordered.append(analyzer)

        for analyzer in self.analyzers:
            visit(analyzer)

        return ordered

    def _should_stop(self, analyzer: BaseAnalyzer) -> bool:
        if self.error_policy == AnalysisErrorPolicy.FAIL_FAST:
            return True

        if self.error_policy == AnalysisErrorPolicy.COLLECT_AND_CONTINUE:
            return False

        return analyzer.required
