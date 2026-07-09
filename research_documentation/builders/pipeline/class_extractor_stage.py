import ast

from research_documentation.builders.pipeline.base_stage import BaseStage
from research_documentation.builders.pipeline.context import PipelineContext


class ClassExtractorStage(BaseStage):

    @property
    def name(self) -> str:
        return "Extract Classes"

    def execute(
        self,
        context: PipelineContext,
    ) -> None:

        for tree in context.ast_trees.values():

            for node in ast.walk(tree):

                if isinstance(node, ast.ClassDef):

                    context.class_nodes[node.name] = node
