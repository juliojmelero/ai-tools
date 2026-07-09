from dataclasses import dataclass, field


@dataclass(slots=True)
class TypeReference:
    """
    Language-independent type description.
    """

    name: str

    arguments: list["TypeReference"] = field(default_factory=list)

    is_optional: bool = False

    BUILTIN_TYPES = {
        "int",
        "float",
        "bool",
        "str",
        "bytes",
        "dict",
        "list",
        "tuple",
        "set",
        "frozenset",
        "Any",
        "None",
        "object",
    }

    COLLECTION_TYPES = {
        "list",
        "set",
        "tuple",
        "frozenset",
    }

    def is_builtin(self) -> bool:
        return self.name in self.BUILTIN_TYPES

    def is_collection(self) -> bool:
        return self.name in self.COLLECTION_TYPES

    def is_dictionary(self) -> bool:
        return self.name == "dict"

    def is_union(self) -> bool:
        return self.name == "Union"

    def is_container(self) -> bool:
        return self.is_collection() or self.is_dictionary()

    def element_type(self):
        if self.is_collection() and self.arguments:
            return self.arguments[0]

        return None

    def key_type(self):
        if self.is_dictionary() and len(self.arguments) >= 1:
            return self.arguments[0]

        return None

    def value_type(self):
        if self.is_dictionary() and len(self.arguments) >= 2:
            return self.arguments[1]

        return None

    def contained_types(self) -> list["TypeReference"]:
        if self.is_collection():
            return [self.element_type()] if self.element_type() else []

        if self.is_dictionary():
            return [self.value_type()] if self.value_type() else []

        if self.is_union():
            return self.arguments

        return [self]

    def __str__(self) -> str:
        if not self.arguments:
            return self.name

        args = ", ".join(
            str(a)
            for a in self.arguments
        )

        return f"{self.name}[{args}]"
