from research_documentation.model.software_model import SoftwareModel


class ImportResolver:
    """
    Resolves imported symbols against the SoftwareModel.
    """

    def resolve_symbol(
        self,
        symbol: str,
        model: SoftwareModel,
        module: str = "",
    ):

        direct = model.get_class(symbol)

        if direct is not None:
            return direct

        module_imports = model.imports_for_module(module)

        qualified = module_imports.get(symbol)

        if qualified is None:
            qualified = model.imports.get(symbol)

        if qualified is None:
            return None

        class_name = qualified.split(".")[-1]

        return model.get_class(class_name)
