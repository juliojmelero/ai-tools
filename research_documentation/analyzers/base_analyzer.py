from abc import ABC, abstractmethod

from research_documentation.analyzers.analysis_context import AnalysisContext
from research_documentation.analyzers.analysis_result import AnalysisResult
from research_documentation.model.software_model import SoftwareModel


class BaseAnalyzer(ABC):
    """
    Base class for SoftwareModel analyzers.
    """

    required = True

    dependencies: list[str] = []

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def analyze(
        self,
        model: SoftwareModel,
        context: AnalysisContext,
    ) -> AnalysisResult:
        raise NotImplementedError
