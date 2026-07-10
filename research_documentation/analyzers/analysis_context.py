from dataclasses import dataclass, field

from research_documentation.analyzers.analysis_result import (
    AnalysisDiagnostic,
    AnalysisResult,
)


@dataclass(slots=True)
class AnalysisContext:
    """
    Shared state for one analysis pipeline run.
    """

    results: dict[str, AnalysisResult] = field(default_factory=dict)

    diagnostics: list[AnalysisDiagnostic] = field(default_factory=list)

    metadata: dict[str, object] = field(default_factory=dict)

    def record(self, result: AnalysisResult) -> None:
        self.results[result.analyzer_name] = result
        self.diagnostics.extend(result.diagnostics)
