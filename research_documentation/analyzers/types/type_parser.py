import ast

from research_documentation.model.types.type_reference import TypeReference


class TypeParser:
    """
    Parses Python type annotations into TypeReference objects.
    """

    OPTIONAL_NAMES = {
        "Optional",
    }

    UNION_NAMES = {
        "Union",
    }

    def parse(
        self,
        annotation,
    ) -> TypeReference:

        if annotation is None:
            return TypeReference("Any")

        if isinstance(annotation, str):
            annotation = ast.parse(
                annotation,
                mode="eval",
            ).body

        if isinstance(annotation, ast.Name):
            return TypeReference(annotation.id)

        if isinstance(annotation, ast.Attribute):
            return TypeReference(annotation.attr)

        if isinstance(annotation, ast.Constant):
            return TypeReference(str(annotation.value))

        if isinstance(annotation, ast.Subscript):
            return self._parse_subscript(annotation)

        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            return self._parse_pipe_union(annotation)

        return TypeReference("Any")

    def _parse_subscript(
        self,
        node: ast.Subscript,
    ) -> TypeReference:

        base = self.parse(node.value)

        args = self._parse_subscript_args(node.slice)

        if base.name in self.OPTIONAL_NAMES:
            if args:
                args[0].is_optional = True
                return args[0]

        if base.name in self.UNION_NAMES:
            return TypeReference(
                name="Union",
                arguments=args,
            )

        return TypeReference(
            name=base.name,
            arguments=args,
        )

    def _parse_subscript_args(
        self,
        node,
    ) -> list[TypeReference]:

        if isinstance(node, ast.Tuple):
            return [
                self.parse(elt)
                for elt in node.elts
            ]

        return [
            self.parse(node)
        ]

    def _parse_pipe_union(
        self,
        node: ast.BinOp,
    ) -> TypeReference:

        left = self.parse(node.left)
        right = self.parse(node.right)

        args = [left, right]

        if any(a.name == "None" for a in args):
            non_none = [
                a
                for a in args
                if a.name != "None"
            ]

            if non_none:
                non_none[0].is_optional = True
                return non_none[0]

        return TypeReference(
            name="Union",
            arguments=args,
        )
