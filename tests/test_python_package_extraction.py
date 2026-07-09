from research_documentation.builders.uml.uml_builder import UMLBuilder
from research_documentation.extractors.python.python_extractor import PythonExtractor


def test_extracts_root_package_name_from_file_path(tmp_path):
    package = tmp_path / "research_models"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "field_value.py").write_text(
        "class FieldValue:\n"
        "    pass\n",
        encoding="utf-8",
    )

    model = PythonExtractor().extract(package)

    software_class = model.get_class("FieldValue")
    assert software_class is not None
    assert software_class.package_name == "research_models"
    assert "research_models" in model.packages
    assert software_class in model.packages["research_models"].classifiers


def test_extracts_nested_package_name_from_file_path(tmp_path):
    package = tmp_path / "research_engine"
    providers = package / "providers"
    providers.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (providers / "__init__.py").write_text("", encoding="utf-8")
    (providers / "openalex.py").write_text(
        "class OpenAlexProvider:\n"
        "    pass\n",
        encoding="utf-8",
    )

    model = PythonExtractor().extract(package)

    software_class = model.get_class("OpenAlexProvider")
    assert software_class is not None
    assert software_class.package_name == "research_engine.providers"
    assert "research_engine.providers" in model.packages
    assert software_class in model.packages["research_engine.providers"].classifiers


def test_uml_builder_remains_compatible_with_package_extraction(tmp_path):
    package = tmp_path / "research_models"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "field_value.py").write_text(
        "class FieldValue:\n"
        "    value: str\n",
        encoding="utf-8",
    )

    software_model = PythonExtractor().extract(package)
    uml_model = UMLBuilder().build(software_model)

    assert "FieldValue" in uml_model.classes
