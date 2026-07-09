from abc import ABC, abstractmethod

from research_documentation.models.diagram import Diagram


class BaseRenderer(ABC):
    """
    Base class for diagram renderers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def render(self, diagram: Diagram) -> str:
        raise NotImplementedError
