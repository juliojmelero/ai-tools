from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Generic, TypeVar

from research_documentation.builders.uml.uml_builder import UMLBuilder
from research_documentation.extractors.python.python_extractor import PythonExtractor
from research_documentation.renderers.plantuml_renderer import PlantUMLRenderer


T = TypeVar("T")


class Registry(Generic[T]):
    """
    Name-based registry for framework extension points.
    """

    def __init__(self) -> None:
        self._providers: dict[str, Callable[[], T]] = {}

    def register(
        self,
        name: str,
        provider: Callable[[], T] | T,
    ) -> None:
        key = self._normalize(name)

        if callable(provider):
            self._providers[key] = provider
            return

        self._providers[key] = lambda: provider

    def get(self, name: str) -> T:
        key = self._normalize(name)

        try:
            provider = self._providers[key]
        except KeyError as exc:
            available = ", ".join(self.names()) or "none"
            raise KeyError(
                f"Unknown registry item '{name}'. Available: {available}"
            ) from exc

        return provider()

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False

        return self._normalize(name) in self._providers

    def _normalize(self, name: str) -> str:
        return name.strip().lower()


class ExtractorRegistry(Registry[object]):
    """
    Registry for language extractors.
    """

    @classmethod
    def defaults(cls) -> "ExtractorRegistry":
        registry = cls()
        registry.register("python", PythonExtractor)
        return registry


class BuilderRegistry(Registry[object]):
    """
    Registry for documentation model builders.
    """

    @classmethod
    def defaults(cls) -> "BuilderRegistry":
        registry = cls()
        registry.register("uml", UMLBuilder)
        return registry


class RendererRegistry(Registry[object]):
    """
    Registry for documentation renderers.
    """

    @classmethod
    def defaults(cls) -> "RendererRegistry":
        registry = cls()
        registry.register("plantuml", PlantUMLRenderer)
        return registry


def normalize_requested(
    requested: str | Iterable[str] | None,
    defaults: tuple[str, ...],
) -> tuple[str, ...]:
    if requested is None:
        return defaults

    if isinstance(requested, str):
        return (requested,)

    return tuple(requested)
