from pathlib import Path

from research_documentation.model.software_model import SoftwareModel
from research_documentation.model.software_package import SoftwarePackage

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

            package_name = self._package_name(
                package_root=package,
                file=file,
            )

            if package_name not in model.packages:
                model.add_package(
                    SoftwarePackage(package_name)
                )

            self.file_extractor.extract(
                file=file,
                model=model,
                package_name=package_name,
            )

        return model

    def _package_name(
        self,
        package_root: Path,
        file: Path,
    ) -> str:

        relative_parent = file.relative_to(package_root).parent

        parts = [package_root.name]
        if relative_parent != Path("."):
            parts.extend(relative_parent.parts)

        return ".".join(parts)
