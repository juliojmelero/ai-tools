import ast

from research_documentation.builders.pipeline.base_stage import BaseStage
from research_documentation.builders.pipeline.context import PipelineContext


class LoadASTStage(BaseStage):

    @property
    def name(self) -> str:
        return "Load AST"

    def execute(
        self,
        context: PipelineContext,
    ) -> None:

        for file in context.package_path.rglob("*.py"):

            if file.name == "__init__.py":
                continue

            context.ast_trees[file] = ast.parse(
                file.read_text(
                    encoding="utf-8"
                )
            )
