from dataclasses import dataclass, field


@dataclass(slots=True)
class ProjectIndex:
    """
    Global index of all symbols in a project.
    """

    classes: dict[str, str] = field(default_factory=dict)

    modules: dict[str, str] = field(default_factory=dict)

    packages: set[str] = field(default_factory=set)

    def add_class(
        self,
        name: str,
        module: str,
    ) -> None:

        self.classes[name] = module

    def add_module(
        self,
        name: str,
        path: str,
    ) -> None:

        self.modules[name] = path

    def add_package(
        self,
        package: str,
    ) -> None:

        self.packages.add(package)
