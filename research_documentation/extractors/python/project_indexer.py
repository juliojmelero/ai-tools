import ast
from pathlib import Path

from research_documentation.model.project_index import ProjectIndex


class ProjectIndexer:
    """
    Builds a global symbol index for a Python project.
    """

    def build(
        self,
        package: str | Path,
    ) -> ProjectIndex:

        package = Path(package)

        index = ProjectIndex()

        index.add_package(package.name)

        for file in package.rglob("*.py"):

            if file.name == "__init__.py":
                continue

            module = file.stem

            index.add_module(
                module,
                str(file),
            )

            tree = ast.parse(
                file.read_text(encoding="utf-8")
            )

            for node in tree.body:

                if isinstance(node, ast.ClassDef):

                    index.add_class(
                        node.name,
                        module,
                    )

        return index
