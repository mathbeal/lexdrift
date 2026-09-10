"""Walk the AST: record what a module defines and what it calls."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
class Definition:
    """A function, a method or a class defined by the project.

    Attributes:
        kind: One of ``function``, ``method`` or ``class``.
        name: The bare identifier, as written.
        qualname: The dotted path within the module, ``Class.method``.
        module: The dotted name of the module holding the definition.
        lineno: The line the definition starts on, 1-indexed.
        docstring: The docstring, if any.
        bases: Base classes, as written, for a class definition.
        decorators: Decorators, as written.
        calls: Dotted calls made in the body.
    """

    kind: str
    name: str
    qualname: str
    module: str
    lineno: int
    docstring: str | None = None
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    @property
    def is_dunder(self) -> bool:
        """Tell whether the name is a language special method.

        Returns:
            True for names such as ``__init__`` or ``__enter__``.
        """
        return self.name.startswith("__") and self.name.endswith("__")


@dataclass
class Module:
    """The outcome of parsing one file.

    Attributes:
        module: The dotted module name.
        path: The file it came from, if read from disk.
        definitions: Everything the module defines.
        imports: Bound name to the module it was imported from.
    """

    module: str
    path: str = ""
    definitions: list[Definition] = field(default_factory=list)
    imports: dict[str, str] = field(default_factory=dict)


def _dotted(node: ast.expr) -> str | None:
    """Render a Name or an Attribute in its dotted form.

    Args:
        node: The expression to render.

    Returns:
        The dotted name, or None for anything else.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted(node.value)
        return prefix + "." + node.attr if prefix else None
    return None


def _calls_in(node: ast.AST) -> list[str]:
    """Collect the dotted calls made inside a body.

    Args:
        node: The subtree to walk.

    Returns:
        Every call whose callee has a dotted name.
    """
    found: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _dotted(child.func)
            if name:
                found.append(name)
    return found


class _Visitor(ast.NodeVisitor):
    """Collect definitions and imports from a single module."""

    def __init__(self, module: str) -> None:
        """Start an empty result for the given module.

        Args:
            module: The dotted name of the module being visited.
        """
        self.result = Module(module=module)
        self._stack: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Record a plain import.

        Args:
            node: The import statement.
        """
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            self.result.imports[bound] = alias.name.split(".")[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Record a from-import, keeping relative levels.

        Args:
            node: The import statement.
        """
        origin = "." * node.level + (node.module or "")
        for alias in node.names:
            self.result.imports[alias.asname or alias.name] = origin

    def _record(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        kind: str,
        bases: tuple[ast.expr, ...] | list[ast.expr] = (),
    ) -> None:
        """Append one definition to the result.

        Args:
            node: The definition node.
            kind: ``function``, ``method`` or ``class``.
            bases: Base classes, for a class definition.
        """
        qualname = ".".join([*self._stack, node.name])
        self.result.definitions.append(
            Definition(
                kind=kind,
                name=node.name,
                qualname=qualname,
                module=self.result.module,
                lineno=node.lineno,
                docstring=ast.get_docstring(node),
                bases=[b for b in (_dotted(b) for b in bases) if b],
                decorators=[d for d in (_dotted(x) for x in node.decorator_list) if d],
                calls=_calls_in(node),
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Record a class and descend into its body.

        Args:
            node: The class definition.
        """
        self._record(node, "class", node.bases)
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Record a function or a method and descend into its body.

        Args:
            node: The function definition.
        """
        self._record(node, "method" if self._stack else "function")
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Record a synchronous function.

        Args:
            node: The function definition.
        """
        self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Record an asynchronous function.

        Args:
            node: The function definition.
        """
        self._function(node)


def collect_source(source: str, module: str = "", path: str = "") -> Module:
    """Collect the definitions and imports of one Python source.

    Args:
        source: The source text to parse.
        module: The dotted name to attach to what is found.
        path: The file the source came from, for reporting.

    Returns:
        Everything the module defines, and what it imports.

    Raises:
        SyntaxError: If the source does not parse.
    """
    visitor = _Visitor(module)
    visitor.result.path = path
    visitor.visit(ast.parse(source))
    return visitor.result
