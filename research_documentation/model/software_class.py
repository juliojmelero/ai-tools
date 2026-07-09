from dataclasses import dataclass, field


@dataclass(slots=True)
class SoftwareClass:
    """
    Language-independent representation of a software class.
    """

    name: str

    module: str = ""

    package: str = ""

    bases: list[str] = field(default_factory=list)

    attributes: list = field(default_factory=list)

    methods: list = field(default_factory=list)

    decorators: list[str] = field(default_factory=list)

    documentation: str = ""

    def add_attribute(self, attribute) -> None:
        self.attributes.append(attribute)

    def add_method(self, method) -> None:
        self.methods.append(method)
