from research_documentation.analyzers import (
    AnalysisContext,
    AnalysisPipeline,
    AnalysisPipelineError,
    AnalysisResult,
    BaseAnalyzer,
    DependencyGraphAnalyzer,
    RelationshipResolverAnalyzer,
    TypeResolverAnalyzer,
)
from research_documentation.model.software_attribute import SoftwareAttribute
from research_documentation.model.software_class import SoftwareClass
from research_documentation.model.software_model import SoftwareModel
from research_documentation.model.software_relationship import (
    SoftwareRelationshipType,
)
from research_documentation.model.types.type_reference import TypeReference


def test_analysis_pipeline_enriches_model_and_sets_dependency_graph():
    model = SoftwareModel("sample")
    profile = SoftwareClass("Profile")
    user = SoftwareClass("User")
    attribute = SoftwareAttribute(
        name="profile",
        type_name="Profile",
        type_reference=TypeReference("Profile"),
    )
    user.add_attribute(attribute)
    model.add_class(profile)
    model.add_class(user)

    AnalysisPipeline(
        [
            DependencyGraphAnalyzer(),
            RelationshipResolverAnalyzer(),
            TypeResolverAnalyzer(),
        ]
    ).run(model)

    assert attribute.resolved_type is profile
    assert len(model.relationships) == 1
    assert model.relationships[0].source is user
    assert model.relationships[0].target is profile
    assert (
        model.relationships[0].relationship_type
        is SoftwareRelationshipType.COMPOSITION
    )
    assert len(model.dependency_graph.dependencies) == 1
    assert model.dependency_graph.dependencies[0].source is user
    assert model.dependency_graph.dependencies[0].target is profile


def test_optional_analyzer_failure_is_recorded_and_pipeline_continues():
    model = SoftwareModel("sample")
    context = AnalysisContext()

    AnalysisPipeline(
        [
            FailingAnalyzer(required=False),
            RecordingAnalyzer(),
        ]
    ).run(model, context=context)

    assert "failing" in context.results
    assert context.results["failing"].success is False
    assert "recording" in context.results
    assert context.results["recording"].success is True
    assert len(context.diagnostics) == 1


def test_required_analyzer_failure_stops_by_default():
    model = SoftwareModel("sample")

    try:
        AnalysisPipeline([FailingAnalyzer(required=True)]).run(model)
    except AnalysisPipelineError:
        return

    raise AssertionError("required analyzer failure did not stop the pipeline")


class FailingAnalyzer(BaseAnalyzer):
    name = "failing"

    def __init__(self, required: bool) -> None:
        self.required = required

    def analyze(
        self,
        model: SoftwareModel,
        context: AnalysisContext,
    ) -> AnalysisResult:
        raise RuntimeError("boom")


class RecordingAnalyzer(BaseAnalyzer):
    name = "recording"

    def analyze(
        self,
        model: SoftwareModel,
        context: AnalysisContext,
    ) -> AnalysisResult:
        return AnalysisResult.ok(self.name)
