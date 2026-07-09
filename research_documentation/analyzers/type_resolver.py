from research_documentation.analyzers.import_resolver import ImportResolver
from research_documentation.model.software_model import SoftwareModel
from research_documentation.model.types.type_reference import TypeReference


class TypeResolver:
    """
    Resolves TypeReference objects against the SoftwareModel.
    """

    def __init__(self):
        self.import_resolver = ImportResolver()

    def resolve(self, model: SoftwareModel) -> None:
        for software_class in model.classifiers:
            for attribute in software_class.attributes:
                attribute.resolved_type = self._resolve_type_reference(
                    attribute.type_reference,
                    model,
                    software_class.module,
                )

    def _resolve_type_reference(
        self,
        type_reference: TypeReference,
        model: SoftwareModel,
        module: str,
    ):
        for contained in type_reference.contained_types():
            if contained is None:
                continue

            if contained.is_builtin():
                continue

            resolved = self.import_resolver.resolve_symbol(
                contained.name,
                model,
                module=module,
            )

            if resolved is not None:
                return resolved

        return None
