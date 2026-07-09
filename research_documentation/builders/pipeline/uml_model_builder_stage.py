from research_documentation.builders.pipeline.base_stage import BaseStage
from research_documentation.builders.pipeline.context import PipelineContext

from research_documentation.models.uml.class_ import UMLClass
from research_documentation.models.uml.model import UMLModel


class UMLModelBuilderStage(BaseStage):

    @property
    def name(self) -> str:
        return "Build UML Model"

    def execute(
        self,
        context: PipelineContext,
    ) -> None:

        model = UMLModel(
            context.package_path.name
        )

        for class_name in sorted(context.class_nodes):

            model.add_class(
                UMLClass(class_name)
            )

        context.uml_model = model
