"""Walk a repository: what is read, what is skipped, what comes out."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .collector import Module, collect_source
from .lexicon import split_chosen_words
from .rules import Finding, load_families, measure
from .vocabulary import classify

SKIPPED = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "site-packages",
    "node_modules",
    "vendor",
    "build",
    "dist",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    ".eggs",
}


@dataclass
class Project:
    """A repository once read.

    Attributes:
        root: The directory that was walked.
        modules: Every file that parsed.
        project_roots: Top-level packages belonging to the project.
        unreadable: Files that failed to parse, with the reason.
    """

    root: str
    modules: list[Module] = field(default_factory=list)
    project_roots: set[str] = field(default_factory=set)
    unreadable: dict[str, str] = field(default_factory=dict)


def _is_environment(current: str, name: str) -> bool:
    """Tell whether a directory is a virtual environment.

    Args:
        current: The directory holding the candidate.
        name: The candidate directory name.

    Returns:
        True when it carries a ``pyvenv.cfg``.
    """
    return os.path.exists(os.path.join(current, name, "pyvenv.cfg"))


def discover(root: str | os.PathLike[str]) -> list[str]:
    """List the Python files of a repository.

    Dependencies and build artefacts are skipped.

    Args:
        root: The directory to walk.

    Returns:
        Paths to every ``.py`` file worth reading, sorted.
    """
    found: list[str] = []
    for current, directories, files in os.walk(str(root)):
        directories[:] = sorted(
            d
            for d in directories
            if d not in SKIPPED
            and not d.endswith(".egg-info")
            and not _is_environment(current, d)
        )
        found.extend(
            os.path.join(current, name) for name in sorted(files) if name.endswith(".py")
        )
    return found


def _module_name(root: str | os.PathLike[str], path: str) -> str:
    """Derive the dotted module name of a file.

    Args:
        root: The directory the path is relative to.
        path: The file to name.

    Returns:
        The dotted name, empty for a root-level ``__init__.py``.
    """
    relative = os.path.relpath(path, str(root))
    without_extension = os.path.splitext(relative)[0]
    parts = [p for p in without_extension.split(os.sep) if p != "__init__"]
    return ".".join(parts)


def inspect(root: str | os.PathLike[str]) -> Project:
    """Inspect a repository, parsing every file it holds.

    Args:
        root: The directory to read.

    Returns:
        The modules, the project roots, and whatever failed to parse.
    """
    project = Project(root=str(root))
    for path in discover(root):
        name = _module_name(root, path)
        try:
            with open(path, encoding="utf-8") as handle:
                project.modules.append(
                    collect_source(handle.read(), module=name, path=path)
                )
        except (SyntaxError, UnicodeDecodeError, OSError) as error:
            project.unreadable[path] = str(error)
        if name:
            project.project_roots.add(name.split(".")[0])
    return project


def findings(project: Project) -> list[Finding]:
    """Measure the project's own vocabulary against itself.

    Args:
        project: The repository to measure.

    Returns:
        Observations, never faults. See :mod:`lexdrift.drift` for faults.
    """
    return measure(project.modules, project_roots=project.project_roots)


def glossary(project: Project) -> dict[str, Any]:
    """Build the lexicon of a project.

    Args:
        project: The repository to read.

    Returns:
        Verbs, nouns, families, how many names were chosen or imposed, and
        why the imposed ones were: a single share would conflate reasons
        that have nothing to do with each other.
    """
    result = classify(project.modules, project.project_roots)
    verbs: Counter[str] = Counter()
    nouns: Counter[str] = Counter()
    index = {verb: family for family, group in load_families().items() for verb in group}

    for definition in result.own:
        words = split_chosen_words(definition.name)
        if not words:
            continue
        head, tail = words[0], words[1:]
        if definition.kind == "class":
            nouns.update(words)
        elif head in index:
            verbs[head] += 1
            nouns.update(tail)
        else:
            nouns.update(words)

    return {
        "verbs": dict(verbs),
        "nouns": dict(nouns),
        "families": _families_used(verbs, index),
        "own": len(result.own),
        "imposed": len(result.imposed),
        "imposed_by_reason": dict(Counter(r for _, r in result.imposed)),
    }


def _families_used(
    verbs: Counter[str], index: dict[str, str]
) -> dict[str, dict[str, int]]:
    """Group the verbs in use by the family they belong to.

    Args:
        verbs: Verb to number of occurrences.
        index: Verb to family.

    Returns:
        Family to its verbs and their counts.
    """
    grouped: dict[str, dict[str, int]] = {}
    for verb, count in verbs.items():
        grouped.setdefault(index[verb], {})[verb] = count
    return grouped


def paths(project: Project) -> dict[str, str]:
    """Map each module to its path relative to the repository root.

    Args:
        project: The repository the modules came from.

    Returns:
        Dotted module name to relative path, with forward slashes.
    """
    return {
        module.module: os.path.relpath(module.path, project.root).replace(os.sep, "/")
        for module in project.modules
        if module.path
    }
