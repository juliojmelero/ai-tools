import ast
from pathlib import Path

from research_documentation.model.software_model import SoftwareModel


class ImportExtractor:
    """
    Extracts imports from one Python module.
    """

    def extract(
        self,
        tree: ast.Module,
        file: Path,
        model: SoftwareModel,
    ) -> None:

        module_name = file.stem

        for node in tree.body:

            if isinstance(node, ast.Import):

                for alias in node.names:

                    model.add_import(
                        alias.asname or alias.name,
                        alias.name,
                        module=module_name,
                    )

            elif isinstance(node, ast.ImportFrom):

                module = node.module or ""

                for alias in node.names:

                    model.add_import(
                        alias.asname or alias.name,
                        f"{module}.{alias.name}",
                        module=module_name,
                    )
