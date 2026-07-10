from dataclasses import dataclass, field


@dataclass(slots=True)
class AnalysisDiagnostic:
    """
    Diagnostic emitted while running an analyzer.
    """

    analyzer_name: str

    message: str

    severity: str = "error"

    exception: Exception | None = None


@dataclass(slots=True)
class AnalysisResult:
    """
    Result returned by one analyzer execution.
    """

    analyzer_name: str

    success: bool = True

    diagnostics: list[AnalysisDiagnostic] = field(default_factory=list)

    @classmethod
    def ok(
        cls,
        analyzer_name: str,
        diagnostics: list[AnalysisDiagnostic] | None = None,
    ) -> "AnalysisResult":
        return cls(
            analyzer_name=analyzer_name,
            success=True,
            diagnostics=diagnostics or [],
        )

    @classmethod
    def failed(
        cls,
        analyzer_name: str,
        message: str,
        exception: Exception | None = None,
    ) -> "AnalysisResult":
        return cls(
            analyzer_name=analyzer_name,
            success=False,
            diagnostics=[
                AnalysisDiagnostic(
                    analyzer_name=analyzer_name,
                    message=message,
                    exception=exception,
                )
            ],
        )
