from research_documentation.builders.pipeline.base_stage import BaseStage
from research_documentation.builders.pipeline.context import PipelineContext


class SymbolTableStage(BaseStage):

    @property
    def name(self) -> str:
        return "Build Symbol Table"

    def execute(
        self,
        context: PipelineContext,
    ) -> None:

        for class_name, class_node in context.class_nodes.items():
            context.symbols[class_name] = class_node
