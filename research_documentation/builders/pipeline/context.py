from dataclasses import dataclass, field
from pathlib import Path
import ast

from research_documentation.models.uml.model import UMLModel


@dataclass(slots=True)
class PipelineContext:
    """
    Shared information between pipeline stages.
    """

    package_path: Path

    ast_trees: dict[Path, ast.Module] = field(default_factory=dict)

    class_nodes: dict[str, ast.ClassDef] = field(default_factory=dict)

    symbols: dict[str, ast.AST] = field(default_factory=dict)

    uml_model: UMLModel | None = None
