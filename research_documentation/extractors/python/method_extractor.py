import ast

from research_documentation.analyzers.types.type_parser import TypeParser
from research_documentation.model.software_class import SoftwareClass
from research_documentation.model.software_method import SoftwareMethod
from research_documentation.model.software_parameter import SoftwareParameter


class MethodExtractor:
    """
    Extracts methods from Python classes.
    """

    def __init__(self):
        self.type_parser = TypeParser()

    def extract(
        self,
        class_node: ast.ClassDef,
        software_class: SoftwareClass,
    ) -> None:

        for node in class_node.body:

            if not isinstance(node, ast.FunctionDef):
                continue

            method = SoftwareMethod(
                name=node.name,
                return_type_name=self._annotation(node.returns),
                return_type=self.type_parser.parse(node.returns),
                decorators=self._decorators(node),
                documentation=ast.get_docstring(node) or "",
            )

            for arg in node.args.args:

                if arg.arg == "self":
                    continue

                method.parameters.append(
                    SoftwareParameter(
                        name=arg.arg,
                        type_name=self._annotation(arg.annotation),
                        type_reference=self.type_parser.parse(arg.annotation),
                    )
                )

            software_class.add_method(method)

    def _decorators(self, node):

        result = []

        for decorator in node.decorator_list:

            if hasattr(ast, "unparse"):
                result.append(ast.unparse(decorator))

        return result

    def _annotation(self, annotation):

        if annotation is None:
            return "Any"

        if hasattr(ast, "unparse"):
            return ast.unparse(annotation)

        return "Any"
