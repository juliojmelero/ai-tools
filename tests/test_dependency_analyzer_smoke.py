from pathlib import Path

from research_documentation.analyzers.dependency.dependency_analyzer import (
    DependencyAnalyzer,
)
from research_documentation.analyzers.relationship_resolver import (
    RelationshipResolver,
)
from research_documentation.analyzers.type_resolver import TypeResolver
from research_documentation.extractors.python.python_extractor import (
    PythonExtractor,
)


def test_dependency_analyzer_smoke():
    model = PythonExtractor().extract(Path("research_models"))

    TypeResolver().resolve(model)
    RelationshipResolver().resolve(model)
    graph = DependencyAnalyzer().analyze(model)

    publication = model.get_class("Publication")
    field_value = model.get_class("FieldValue")
    provider_value = model.get_class("ProviderValue")

    assert publication is not None
    assert field_value is not None
    assert provider_value is not None
    assert field_value in graph.dependencies_of(publication)
    assert provider_value in graph.dependencies_of(field_value)
