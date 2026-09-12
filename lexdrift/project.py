"""Walk a repository: what is read, what is skipped, what comes out."""

from __future__ import annotations

import operator
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .collector import Module, collect_source
from .config import load_config
from .rules import Finding, load_compounds, load_families, measure, split_name
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
    return (Path(current) / name / "pyvenv.cfg").exists()


def discover(root: str | os.PathLike[str]) -> list[Path]:
    """List the Python files of a repository.

    Dependencies and build artefacts are skipped.

    Args:
        root: The directory to walk.

    Returns:
        Paths to every ``.py`` file worth reading, sorted.
    """
    found: list[Path] = []
    # Path.walk arrived in 3.12 and the floor is 3.11: os.walk stays.
    for current, directories, files in os.walk(str(root)):
        directories[:] = sorted(
            d
            for d in directories
            if d not in SKIPPED
            and not d.endswith(".egg-info")
            and not _is_environment(current, d)
        )
        found.extend(
            Path(current) / name for name in sorted(files) if name.endswith(".py")
        )
    return found


def _module_name(root: str | os.PathLike[str], path: Path) -> str:
    """Derive the dotted module name of a file.

    Args:
        root: The directory the path is relative to.
        path: The file to name.

    Returns:
        The dotted name, empty for a root-level ``__init__.py``.
    """
    relative = path.relative_to(root).with_suffix("")
    return ".".join(p for p in relative.parts if p != "__init__")


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
            with path.open(encoding="utf-8") as handle:
                project.modules.append(
                    collect_source(handle.read(), module=name, path=str(path))
                )
        except (SyntaxError, UnicodeDecodeError, OSError) as error:
            project.unreadable[str(path)] = str(error)
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
    return measure(
        project.modules,
        project_roots=project.project_roots,
        nouns=load_config(project.root),
    )


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
    compounds = load_compounds()

    for definition in result.own:
        verb, carried = split_name(definition, index, compounds)
        if verb:
            verbs[verb] += 1
        nouns.update(carried)

    return {
        "verbs": dict(verbs),
        "nouns": dict(nouns),
        "families": _families_used(verbs, index),
        "own": len(result.own),
        "imposed": len(result.imposed),
        "imposed_by_reason": dict(Counter(r for _, r in result.imposed)),
    }


@dataclass(frozen=True)
class Narrowing:
    """How much of a lexicon to keep, and which half of it.

    Attributes:
        most_common: Keep only the N most used words of each kind.
        least_common: Keep only the N least used words of each kind.
        min_count: Drop words used fewer times than this.
        max_count: Drop words used more times than this.
        kind: ``all``, ``verbs`` or ``nouns``.
    """

    most_common: int | None = None
    least_common: int | None = None
    min_count: int | None = None
    max_count: int | None = None
    kind: str = "all"

    def __post_init__(self) -> None:
        """Refuse a request for both ends of one list.

        Raises:
            ValueError: When most_common and least_common are both given.
        """
        if self.most_common is not None and self.least_common is not None:
            message = "most_common and least_common ask for opposite ends of one list"
            raise ValueError(message)

    @property
    def narrows(self) -> bool:
        """Whether anything at all was asked to be dropped."""
        return self.kind != "all" or any(
            value is not None
            for value in (
                self.most_common,
                self.least_common,
                self.min_count,
                self.max_count,
            )
        )


def filter_lexicon(
    lexicon: dict[str, Any], narrowing: Narrowing | None = None
) -> dict[str, Any]:
    """Narrow a lexicon to the part worth reading.

    The head of the list says what a repository is about. The tail is where
    drift hides: a word used once is either a concept of its own or a synonym
    that escaped. Corpus totals are never narrowed — they describe the whole.

    Args:
        lexicon: The glossary to narrow.
        narrowing: What to keep. Defaults to keeping everything.

    Returns:
        The same lexicon, with its word lists narrowed and its families
        recomputed from the verbs that survived.
    """
    asked = narrowing if narrowing is not None else Narrowing()
    most_common, least_common = asked.most_common, asked.least_common
    min_count, max_count = asked.min_count, asked.max_count

    def narrow(counts: dict[str, int]) -> dict[str, int]:
        kept = {
            word: n
            for word, n in counts.items()
            if (min_count is None or n >= min_count)
            and (max_count is None or n <= max_count)
        }
        if most_common is not None:
            order = sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))[:most_common]
            return dict(order)
        if least_common is not None:
            order = sorted(kept.items(), key=operator.itemgetter(1, 0))[:least_common]
            return dict(order)
        return kept

    verbs = {} if asked.kind == "nouns" else narrow(lexicon["verbs"])
    nouns = {} if asked.kind == "verbs" else narrow(lexicon["nouns"])
    index = {verb: family for family, group in load_families().items() for verb in group}
    return {
        **lexicon,
        "verbs": verbs,
        "nouns": nouns,
        "families": _families_used(Counter(verbs), index),
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
        module.module: Path(module.path).relative_to(project.root).as_posix()
        for module in project.modules
        if module.path
    }
