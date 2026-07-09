from research_documentation import (
    BuilderRegistry,
    DocumentationEngine,
    ExtractorRegistry,
    RendererRegistry,
)
from research_documentation.analyzers import AnalysisPipeline
from research_documentation.model.software_class import SoftwareClass
from research_documentation.model.software_model import SoftwareModel


def test_generate_uses_default_python_uml_plantuml_pipeline(tmp_path):
    package = tmp_path / "research_models"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "publication.py").write_text(
        "class Publication:\n"
        "    title: str\n",
        encoding="utf-8",
    )

    result = DocumentationEngine().generate(
        path=package,
        language="python",
    )

    assert result.software_model.get_class("Publication") is not None
    assert "uml" in result.built_models
    assert len(result.artifacts) == 1
    assert result.artifacts[0].builder == "uml"
    assert result.artifacts[0].renderer == "plantuml"
    assert "class Publication" in result.artifacts[0].content


def test_generate_orchestrates_injected_components_without_user_analyzers():
    events = []
    model = SoftwareModel("sample")
    model.add_class(SoftwareClass("Publication"))

    extractor_registry = ExtractorRegistry()
    extractor_registry.register(
        "testlang",
        lambda: RecordingExtractor(events, model),
    )

    builder_registry = BuilderRegistry()
    builder_registry.register("summary", lambda: RecordingBuilder(events))

    renderer_registry = RendererRegistry()
    renderer_registry.register("text", lambda: RecordingRenderer(events))

    engine = DocumentationEngine(
        extractor_registry=extractor_registry,
        builder_registry=builder_registry,
        renderer_registry=renderer_registry,
        analysis_pipeline=RecordingPipeline(events),
        default_builders=("summary",),
        default_renderers=("text",),
    )

    result = engine.generate(path="src", language="testlang")

    assert events == [
        ("extract", "src"),
        ("analyze", "sample"),
        ("build", "sample"),
        ("render", "sample-summary"),
    ]
    assert result.artifacts[0].content == "rendered sample-summary"


def test_registries_allow_new_languages_builders_and_renderers():
    extractors = ExtractorRegistry()
    builders = BuilderRegistry()
    renderers = RendererRegistry()

    extractors.register("java", lambda: object())
    builders.register("c4", lambda: object())
    renderers.register("mermaid", lambda: object())

    assert "java" in extractors
    assert "c4" in builders
    assert "mermaid" in renderers


class RecordingExtractor:
    def __init__(self, events, model):
        self.events = events
        self.model = model

    def extract(self, path):
        self.events.append(("extract", path))
        return self.model


class RecordingPipeline(AnalysisPipeline):
    def __init__(self, events):
        super().__init__([])
        self.events = events

    def run(self, model, context=None):
        self.events.append(("analyze", model.name))
        return model


class RecordingBuilder:
    def __init__(self, events):
        self.events = events

    def build(self, software_model):
        self.events.append(("build", software_model.name))
        return {"name": f"{software_model.name}-summary"}


class RecordingRenderer:
    def __init__(self, events):
        self.events = events

    def render(self, model):
        self.events.append(("render", model["name"]))
        return f"rendered {model['name']}"
