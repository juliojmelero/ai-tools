from abc import ABC, abstractmethod


class BaseGenerator(ABC):
    """
    Base class for every documentation generator.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Generator name."""
        raise NotImplementedError

    @abstractmethod
    def generate(self) -> None:
        """Execute the generator."""
        raise NotImplementedError
