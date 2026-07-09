from pathlib import Path

from research_documentation.generators.base_generator import BaseGenerator
from research_documentation.models.uml.model import UMLModel
from research_documentation.renderers.plantuml_renderer import PlantUMLRenderer


class PlantUMLGenerator(BaseGenerator):
    """
    Generates PlantUML source files from UMLModel objects.
    """

    def __init__(self):
        self.renderer = PlantUMLRenderer()

    @property
    def name(self) -> str:
        return "PlantUML Generator"

    def generate(
        self,
        model: UMLModel,
        output_file: Path,
    ) -> None:
        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        source = self.renderer.render(model)

        output_file.write_text(
            source,
            encoding="utf-8",
        )

        print(f"Generated: {output_file}")
