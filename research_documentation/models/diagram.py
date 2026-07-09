from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DiagramType(Enum):
    CLASS = "class"
    COMPONENT = "component"
    SEQUENCE = "sequence"
    STATE = "state"
    ACTIVITY = "activity"
    DEPLOYMENT = "deployment"
    PACKAGE = "package"
    ER = "er"
    C4 = "c4"


@dataclass(slots=True)
class Diagram:
    """
    Technology-independent representation of a documentation diagram.

    The model knows nothing about PlantUML, Mermaid or any other
    rendering technology.
    """

    id: str
    title: str
    diagram_type: DiagramType

    source_file: Path
    output_directory: Path

    description: str = ""

    generated_files: list[Path] = field(default_factory=list)

    def add_generated_file(self, file: Path) -> None:
        self.generated_files.append(file)

    @property
    def stem(self) -> str:
        return self.source_file.stem

    @property
    def extension(self) -> str:
        return self.source_file.suffix

    @property
    def svg_file(self) -> Path:
        return self.output_directory / f"{self.stem}.svg"

    @property
    def png_file(self) -> Path:
        return self.output_directory / f"{self.stem}.png"

    @property
    def pdf_file(self) -> Path:
        return self.output_directory / f"{self.stem}.pdf"

    def __str__(self) -> str:
        return f"{self.diagram_type.value}: {self.title}"
