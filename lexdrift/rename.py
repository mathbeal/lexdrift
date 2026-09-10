"""Assisted renaming: what can be proven, and an admission of the rest.

Renaming is not a lint fix. A renamed public function breaks its callers,
and Python does not let you enumerate them: dynamic access, strings,
templates. So the tool does the mechanical part, refuses to invent the
rest, and **lists what it could not see**.

The AST is used only to locate. Edits are applied to the text, right to
left, so the file stays byte-for-byte identical outside the positions that
changed.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field

from .project import SKIPPED, discover

TEXT_SUFFIXES = (
    ".html",
    ".htm",
    ".txt",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".cfg",
    ".ini",
    ".sql",
    ".js",
    ".ts",
    ".jinja",
    ".j2",
    ".rst",
    ".csv",
)
DYNAMIC = {"getattr", "setattr", "hasattr", "delattr"}


@dataclass
class Unresolved:
    """Une occurrence que l'outil refuse de toucher, et pourquoi."""

    path: str
    lineno: int
    kind: str
    text: str


@dataclass
class Report:
    """What was renamed, what was not, and why.

    Attributes:
        renamed: Number of occurrences rewritten.
        files: Files that were touched, relative to the root.
        warnings: Occurrences left alone, each with its reason.
        refusal: Why the whole rename was refused, if it was.
    """

    renamed: int = 0
    files: list[str] = field(default_factory=list)
    warnings: list[Unresolved] = field(default_factory=list)
    refusal: str | None = None


def _as_written(node: ast.Attribute) -> str:
    """Rend ``objet.attribut`` tel qu'il se lit."""
    owner = getattr(node.value, "id", "…")
    return f"{owner}.{node.attr}"


class _Sites(ast.NodeVisitor):
    """Locate the safe positions and flag the others."""

    def __init__(self, old: str, new: str, path: str) -> None:
        self.old = old
        self.new = new
        self.path = path
        self.positions: list[tuple[int, int]] = []
        self.lines: list[int] = []
        self.warnings: list[Unresolved] = []
        self.collision = False
        self._owner: list[bool] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        methods = [
            child.name
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if self.new in methods:
            self.collision = True
        self._owner.append(self.old in methods)
        self.generic_visit(node)
        self._owner.pop()

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name == self.old:
            self.lines.append(node.lineno)
        if node.name == self.new and not self._owner:
            self.collision = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == self.old:
            self.positions.append((node.lineno, node.col_offset))
        elif node.id == self.new:
            self.collision = True

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == self.old:
            on_self = isinstance(node.value, ast.Name) and node.value.id == "self"
            if on_self and self._owner and self._owner[-1]:
                end = node.end_col_offset or 0
                self.positions.append(
                    (node.end_lineno or node.lineno, end - len(self.old))
                )
            else:
                self.warnings.append(
                    Unresolved(self.path, node.lineno, "attribute", _as_written(node))
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if any(alias.name == self.old for alias in node.names):
            self.lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        if any(alias.name.split(".")[-1] == self.old for alias in node.names):
            self.lines.append(node.lineno)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and re.search(
            rf"\b{re.escape(self.old)}\b", node.value
        ):
            self.warnings.append(
                Unresolved(self.path, node.lineno, "string", repr(node.value))
            )

    def visit_Call(self, node: ast.Call) -> None:
        target = node.func.id if isinstance(node.func, ast.Name) else None
        if target in DYNAMIC:
            for argument in node.args:
                if isinstance(argument, ast.Constant) and argument.value == self.old:
                    self.warnings.append(
                        Unresolved(
                            self.path,
                            node.lineno,
                            "dynamic access",
                            f"{target}(…, {self.old!r})",
                        )
                    )
        self.generic_visit(node)


def _edit(
    source: str,
    old: str,
    new: str,
    positions: list[tuple[int, int]],
    lines: list[int],
) -> tuple[str, int]:
    """Edit the source, leaving the rest of the text untouched.

    Args:
        source: The file content.
        old: The name to replace.
        new: The name to write.
        positions: Certain positions, as line and column.
        lines: Lines to scan for whole-word matches.

    Returns:
        The rewritten text and how many occurrences changed.
    """
    rows = source.splitlines(keepends=True)
    word = re.compile(rf"\b{re.escape(old)}\b")
    columns: dict[int, set[int]] = {}
    for lineno, column in positions:
        columns.setdefault(lineno, set()).add(column)
    for lineno in lines:
        for match in word.finditer(rows[lineno - 1]):
            columns.setdefault(lineno, set()).add(match.start())

    count = 0
    for lineno, starts in columns.items():
        row = rows[lineno - 1]
        for start in sorted(starts, reverse=True):
            if row[start : start + len(old)] != old:
                continue  # pragma: no cover - garde-fou de position
            row = row[:start] + new + row[start + len(old) :]
            count += 1
        rows[lineno - 1] = row
    return "".join(rows), count


def _foreign_files(root: str | os.PathLike[str], old: str) -> list[Unresolved]:
    """Les occurrences hors Python : gabarits, JSON, SQL, migrations."""
    found: list[Unresolved] = []
    word = re.compile(rf"\b{re.escape(old)}\b")
    for current, directories, files in os.walk(str(root)):
        directories[:] = [d for d in directories if d not in SKIPPED]
        for name in sorted(files):
            if not name.endswith(TEXT_SUFFIXES):
                continue
            path = os.path.join(current, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    for number, line in enumerate(handle, 1):
                        if word.search(line):
                            found.append(
                                Unresolved(path, number, "non-Python", line.strip())
                            )
            except (UnicodeDecodeError, OSError):
                continue
    return found


def rename(
    root: str | os.PathLike[str],
    old: str,
    new: str,
    *,
    dry_run: bool = False,
) -> Report:
    """Rename what can be proven, flag everything else.

    Args:
        root: The repository to walk.
        old: The name to replace.
        new: The name to write.
        dry_run: Report without writing anything.

    Returns:
        What changed, what did not, and why.
    """
    report = Report()
    plans: list[tuple[str, str, _Sites]] = []

    for path in discover(root):
        try:
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        sites = _Sites(old, new, path)
        sites.visit(tree)
        if sites.collision and (sites.positions or sites.lines):
            report.refusal = f'"{new}" already exists in the same scope: rename refused'
            return report
        report.warnings.extend(sites.warnings)
        if sites.positions or sites.lines:
            plans.append((path, source, sites))

    for path, source, sites in plans:
        rewritten, count = _edit(source, old, new, sites.positions, sites.lines)
        report.renamed += count
        report.files.append(path)
        if not dry_run and count:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(rewritten)

    report.warnings.extend(_foreign_files(root, old))
    for warning in report.warnings:
        warning.path = os.path.relpath(warning.path, str(root)).replace(os.sep, "/")
    report.files = [
        os.path.relpath(p, str(root)).replace(os.sep, "/") for p in report.files
    ]
    return report
