from pathlib import Path

from research_documentation.model.software_model import SoftwareModel

from research_documentation.extractors.python.file_extractor import FileExtractor


class PythonExtractor:
    """
    Extracts a SoftwareModel from a Python package.
    """

    def __init__(self):

        self.file_extractor = FileExtractor()

    def extract(
        self,
        package: str | Path,
    ) -> SoftwareModel:

        package = Path(package)

        model = SoftwareModel(
            package.name
        )

        for file in sorted(package.rglob("*.py")):

            if file.name == "__init__.py":
                continue

            self.file_extractor.extract(
                file=file,
                model=model,
            )

        return model
