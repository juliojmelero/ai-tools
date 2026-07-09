from abc import ABC, abstractmethod

from research_documentation.builders.pipeline.context import PipelineContext


class BaseStage(ABC):
    """
    Base class for every pipeline stage.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        context: PipelineContext,
    ) -> None:
        """
        Executes one pipeline stage.
        """
        raise NotImplementedError
