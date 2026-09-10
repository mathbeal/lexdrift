"""What a vocabulary linter can legitimately fail on.

An imperfect lexicon is not a fault: it is the normal state of any
repository with some history. Failing a build because a project uses four
verbs for converting is how a tool gets uninstalled within two days.

What *is* a fault is **drift**: a new word for an idea the repository
already named. It is local, it is recent, it was your doing, and it is
fixed by renaming one function.

The baseline comes from ``lexdrift dump`` and is meant to be committed.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import TYPE_CHECKING, Any

from .lexicon import split_identifier
from .rules import (
    Finding,
    _docstring_disagreement,
    _verb_index,
    load_abbreviations,
    load_families,
)
from .vocabulary import classify

if TYPE_CHECKING:
    from .collector import Definition
    from .project import Project

Baseline = Mapping[str, Any]
AMBIGUOUS = 2  # past one verb, the family is named several ways


def _established(baseline: Baseline | None) -> dict[str, set[str]]:
    """Read the verbs already in use in the baseline.

    Args:
        baseline: The accepted state, or None.

    Returns:
        Family to the verbs it was already named with.
    """
    if not baseline:
        return {}
    families: Mapping[str, Iterable[str]] = baseline.get("families", {})
    return {family: set(verbs) for family, verbs in families.items()}


def _known_words(baseline: Baseline | None) -> set[str]:
    """Read every word the baseline already knew.

    Args:
        baseline: The accepted state, or None.

    Returns:
        Verbs and nouns alike, as one set.
    """
    if not baseline:
        return set()
    return set(baseline.get("nouns", {})) | set(baseline.get("verbs", {}))


def compare(project: Project, baseline: Baseline | None = None) -> list[Finding]:
    """Report the faults that can be repaired.

    Verb drift, abbreviation drift, and disagreement between a name and its
    docstring.

    Args:
        project: The repository to check.
        baseline: The accepted state, or None to report everything.

    Returns:
        Findings, sorted by module then line.
    """
    own = classify(project.modules, project.project_roots).own
    functions = [d for d in own if d.kind in ("function", "method")]
    verbs = _verb_index(load_families())
    findings = [
        *_verb_drift(functions, verbs, _established(baseline)),
        *_abbreviation_drift(own, _known_words(baseline)),
        *(
            Finding("D003", f.message, f.module, f.lineno, f.qualname)
            for f in _docstring_disagreement(functions, verbs)
        ),
    ]
    return sorted(findings, key=lambda f: (f.module, f.lineno, f.rule))


def _verb_drift(
    functions: Iterable[Definition],
    verbs: Mapping[str, str],
    established: Mapping[str, set[str]],
) -> list[Finding]:
    """Report a new verb in a family the repository already named.

    With no baseline, the established verb is taken to be the most used one.

    Args:
        functions: The definitions to read.
        verbs: Verb to family.
        established: Family to the verbs the baseline accepted.

    Returns:
        One finding per newcomer verb.
    """
    seen: dict[str, dict[str, Definition]] = {}
    counts: dict[str, int] = {}
    for definition in functions:
        words = split_identifier(definition.name)
        head = words[0] if words else None
        if head is not None and head in verbs:
            seen.setdefault(verbs[head], {}).setdefault(head, definition)
            counts[head] = counts.get(head, 0) + 1

    findings: list[Finding] = []
    for family, occurrences in sorted(seen.items()):
        accepted = established.get(family, set())
        if accepted:
            newcomers = sorted(set(occurrences) - accepted)
            reference = sorted(accepted)
        else:
            if len(occurrences) < AMBIGUOUS:
                continue
            # with no baseline, the established verb is the most used one
            ordered = sorted(occurrences, key=lambda v: (-counts[v], v))
            newcomers, reference = sorted(ordered[1:]), ordered[:1]
        for verb in newcomers:
            definition = occurrences[verb]
            findings.append(
                Finding(
                    "D001",
                    f'"{verb}" is new for the idea "{family}", '
                    f"already named by {', '.join(reference)}",
                    definition.module,
                    definition.lineno,
                    definition.qualname,
                )
            )
    return findings


def _abbreviation_drift(
    definitions: Iterable[Definition], known: Collection[str]
) -> list[Finding]:
    """Report a new abbreviation of a word the repository spells out.

    Args:
        definitions: The definitions to read.
        known: Words the baseline already knew.

    Returns:
        One finding per new abbreviation.
    """
    table = load_abbreviations()
    sites: dict[str, Definition] = {}
    present: set[str] = set()
    for definition in definitions:
        for word in split_identifier(definition.name):
            present.add(word)
            sites.setdefault(word, definition)

    findings: list[Finding] = []
    for short in sorted(present & set(table)):
        if short in known:
            continue
        for long_word in table[short]:
            if long_word in present:
                definition = sites[short]
                findings.append(
                    Finding(
                        "D002",
                        f'"{short}" abbreviates "{long_word}", '
                        f"which this repository spells out",
                        definition.module,
                        definition.lineno,
                        definition.qualname,
                    )
                )
    return findings
