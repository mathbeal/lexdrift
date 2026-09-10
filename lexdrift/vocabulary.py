"""Separate the vocabulary a project chose from the one imposed on it.

A name imposed by a framework — ``get_queryset`` under Django, ``test_*``
under pytest, ``__enter__`` by the language itself — is not a decision by
the author. Judging it would be noisy and wrong: it cannot be renamed.
Those names are not discarded, they are set aside with the reason why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from .collector import Definition, Module

CONVENTION_PREFIXES = ("test_",)


@dataclass
class Classification:
    """What the project named itself, and what was imposed on it.

    Attributes:
        own: Definitions the author was free to name.
        imposed: Definitions that were not a choice, each with its reason.
    """

    own: list[Definition] = field(default_factory=list)
    imposed: list[tuple[Definition, str]] = field(default_factory=list)


def _is_third_party(
    dotted: str, imports: dict[str, str], project_roots: Collection[str]
) -> bool:
    """Tell whether a dotted name comes from outside the project.

    Args:
        dotted: The name as written, possibly dotted.
        imports: Bound name to the module it was imported from.
        project_roots: Top-level packages belonging to the project.

    Returns:
        True when the name resolves to a third-party library.
    """
    root = dotted.split(".", maxsplit=1)[0]
    origin = imports.get(root)
    if origin is None or origin.startswith("."):
        return False
    return origin.split(".")[0] not in project_roots


def classify(
    modules: Iterable[Module], project_roots: Collection[str] = frozenset()
) -> Classification:
    """Split definitions between chosen and imposed vocabulary.

    Args:
        modules: The parsed modules to sort.
        project_roots: Top-level packages belonging to the project.

    Returns:
        The two groups, the imposed one carrying its reason.
    """
    result = Classification()
    for module in modules:
        imports = module.imports
        foreign_classes = {
            d.name
            for d in module.definitions
            if d.kind == "class"
            and any(_is_third_party(b, imports, project_roots) for b in d.bases)
        }
        for definition in module.definitions:
            reason = _reason(definition, imports, project_roots, foreign_classes)
            if reason:
                result.imposed.append((definition, reason))
            else:
                result.own.append(definition)
    return result


def _reason(
    definition: Definition,
    imports: dict[str, str],
    project_roots: Collection[str],
    foreign_classes: Collection[str],
) -> str | None:
    """Explain why a name was not the author's decision.

    Args:
        definition: The definition under scrutiny.
        imports: Bound name to the module it was imported from.
        project_roots: Top-level packages belonging to the project.
        foreign_classes: Classes deriving from a third-party base.

    Returns:
        The reason, or None when the name was freely chosen.
    """
    if definition.is_dunder:
        return "language special method"
    if definition.name.startswith(CONVENTION_PREFIXES):
        return "tool convention"
    if any(_is_third_party(d, imports, project_roots) for d in definition.decorators):
        return "third-party decorator"
    owner = definition.qualname.rsplit(".", 1)[0] if "." in definition.qualname else None
    if owner in foreign_classes:
        return "third-party base class"
    return None
