import ast
from pathlib import Path

from research_documentation.extractors.python.class_extractor import ClassExtractor
from research_documentation.extractors.python.import_extractor import ImportExtractor

from research_documentation.model.software_model import SoftwareModel


class FileExtractor:

    def __init__(self):

        self.import_extractor = ImportExtractor()
        self.class_extractor = ClassExtractor()

    def extract(
        self,
        file: Path,
        model: SoftwareModel,
    ) -> None:

        source = file.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source,
            filename=str(file),
        )

        self.import_extractor.extract(
            tree=tree,
            file=file,
            model=model,
        )

        self.class_extractor.extract(
            tree=tree,
            file=file,
            model=model,
        )
