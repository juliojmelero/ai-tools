from research_documentation.model.software_class import SoftwareClass
from research_documentation.model.software_model import SoftwareModel
from research_documentation.model.software_package import SoftwarePackage


def test_model_does_not_create_root_package():
    model = SoftwareModel("system")

    assert model.packages == []


def test_add_class_stores_classifier_without_package_assignment():
    model = SoftwareModel("system")
    classifier = SoftwareClass("Publication")

    model.add_class(classifier)

    assert model.get_class("Publication") is classifier
    assert classifier.package_name == ""
    assert model.classifiers == [classifier]
    assert model.classes == {"Publication": classifier}


def test_add_package_uses_list_as_canonical_representation():
    model = SoftwareModel("system")
    package = SoftwarePackage("domain")

    model.add_package(package)
    model.add_package(package)

    assert model.packages == [package]
    assert model.get_package("domain") is package


def test_package_contains_classifiers_by_package_name():
    package = SoftwarePackage("domain")
    classifier = SoftwareClass("Publication")

    package.add_classifier(classifier)

    assert classifier.package_name == "domain"
    assert package.classifiers == [classifier]


def test_classifier_cannot_belong_to_multiple_packages():
    first_package = SoftwarePackage("domain")
    second_package = SoftwarePackage("api")
    classifier = SoftwareClass("Publication")

    first_package.add_classifier(classifier)

    try:
        second_package.add_classifier(classifier)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected classifier package reassignment to fail")


def test_add_subpackage_sets_parent():
    parent = SoftwarePackage("domain")
    child = SoftwarePackage("publication")

    parent.add_subpackage(child)

    assert child.parent is parent
    assert parent.subpackages == [child]
