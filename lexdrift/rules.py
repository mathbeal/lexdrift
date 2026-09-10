"""What can be measured from a lexicon.

A measurement is not a fault: "this repository uses four verbs for
converting" describes a corpus, it condemns nobody. These observations
feed ``lexdrift dump``. What one can legitimately fail on lives in
:mod:`lexdrift.drift`.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .lexicon import split_chosen_words

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from .collector import Definition, Module

_TABLE_PATH = os.path.join(os.path.dirname(__file__), "synonyms.json")
_ABBREVIATION_PATH = os.path.join(os.path.dirname(__file__), "abbreviations.json")
_COMPOUND_PATH = os.path.join(os.path.dirname(__file__), "compounds.json")
ANNOUNCES_A_RETURN = "return"
_VOWELS = set("aeiouy")
AMBIGUOUS = 2  # past one verb, the family is named several ways


@dataclass
class Finding:
    """One observation, located in the code.

    Attributes:
        rule: The rule identifier.
        message: What was observed, in plain words.
        module: The dotted module it was found in.
        lineno: The line it anchors to, 1-indexed.
        qualname: The definition it concerns.
    """

    rule: str
    message: str
    module: str
    lineno: int
    qualname: str


def load_families(path: str = _TABLE_PATH) -> dict[str, list[str]]:
    """Load the table of verb families.

    Args:
        path: Where to read the table from.

    Returns:
        Family name to the verbs that belong to it.
    """
    with open(path, encoding="utf-8") as handle:
        table: dict[str, list[str]] = json.load(handle)
    return table


def load_abbreviations(path: str = _ABBREVIATION_PATH) -> dict[str, list[str]]:
    """Load the table of known abbreviations.

    Args:
        path: Where to read the table from.

    Returns:
        Abbreviation to the words it stands for.
    """
    with open(path, encoding="utf-8") as handle:
        table: dict[str, list[str]] = json.load(handle)
    return table


def load_compounds(path: str = _COMPOUND_PATH) -> list[str]:
    """Load the declared multi-word terms.

    Args:
        path: Where to read the list from.

    Returns:
        Terms, each written as a space-separated phrase.
    """
    with open(path, encoding="utf-8") as handle:
        terms: list[str] = json.load(handle)
    return terms


def _verb_index(families: Mapping[str, Iterable[str]]) -> dict[str, str]:
    """Invert the family table.

    Args:
        families: Family name to its verbs.

    Returns:
        Verb to the family it belongs to.
    """
    return {verb: family for family, verbs in families.items() for verb in verbs}


def _leading_verb(definition: Definition, verbs: Mapping[str, str]) -> str | None:
    """Find the verb a name opens with.

    Args:
        definition: The definition to read.
        verbs: Verb to family.

    Returns:
        The leading verb, or None when the first word is not one.
    """
    words = split_chosen_words(definition.name)
    return words[0] if words and words[0] in verbs else None


def _strip_accents(word: str) -> str:
    """Strip accents from a word.

    Args:
        word: The word to flatten.

    Returns:
        The same word with bare vowels.
    """
    table = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
    return word.translate(table)


def _docstring_verb(definition: Definition, verbs: Mapping[str, str]) -> str | None:
    """Find the verb a docstring opens with.

    Args:
        definition: The definition to read.
        verbs: Verb to family.

    Returns:
        The leading verb, or None when the first word is not one.
    """
    if not definition.docstring:
        return None
    first = re.split(r"[^\w]+", definition.docstring.strip().lower(), maxsplit=1)[0]
    first = _strip_accents(first)
    return first if first in verbs else None


def _third_party_roots(
    definition: Definition, imports: Mapping[str, str], project_roots: Collection[str]
) -> set[str]:
    """List the third-party libraries a body calls into.

    Args:
        definition: The definition to read.
        imports: Bound name to the module it came from.
        project_roots: Top-level packages belonging to the project.

    Returns:
        The roots of every third-party call made in the body.
    """
    roots: set[str] = set()
    for call in definition.calls:
        root = call.split(".")[0]
        origin = imports.get(root)
        if (
            origin
            and not origin.startswith(".")
            and origin.split(".")[0] not in project_roots
        ):
            roots.add(root)
    return roots


def measure(
    modules: Iterable[Module],
    project_roots: Collection[str] = frozenset(),
    families: Mapping[str, list[str]] | None = None,
) -> list[Finding]:
    """Measure the project's own vocabulary against itself.

    Args:
        modules: The parsed modules to read.
        project_roots: Top-level packages belonging to the project.
        families: Verb families to use. Defaults to the shipped table.

    Returns:
        Observations, sorted by module then line.
    """
    from .vocabulary import classify  # noqa: PLC0415 - avoids an import cycle

    modules = list(modules)
    classification = classify(modules, project_roots)
    imports = {m.module: m.imports for m in modules}
    verbs = _verb_index(families or load_families())
    functions = [d for d in classification.own if d.kind in ("function", "method")]
    findings = [
        *_synonyms(functions, verbs),
        *_missing_verb(functions, verbs),
        *_docstring_disagreement(functions, verbs),
        *_abbreviations(classification.own),
        *_polysemy(functions, verbs, imports, project_roots),
    ]
    return sorted(findings, key=lambda f: (f.module, f.lineno, f.rule))


def _synonyms(functions: Iterable[Definition], verbs: Mapping[str, str]) -> list[Finding]:
    """Report families named by more than one verb.

    Args:
        functions: The definitions to read.
        verbs: Verb to family.

    Returns:
        One observation per family named several ways.
    """
    used: dict[str, dict[str, Definition]] = defaultdict(dict)
    for definition in functions:
        verb = _leading_verb(definition, verbs)
        if verb:
            used[verbs[verb]].setdefault(verb, definition)

    findings: list[Finding] = []
    for family, occurrences in used.items():
        if len(occurrences) < AMBIGUOUS:
            continue
        chosen = sorted(occurrences)
        first = occurrences[chosen[0]]
        findings.append(
            Finding(
                "L001",
                f'family "{family}": {len(chosen)} verbs for one idea '
                f"— {', '.join(chosen)}",
                first.module,
                first.lineno,
                first.qualname,
            )
        )
    return findings


def _missing_verb(
    functions: Iterable[Definition], verbs: Mapping[str, str]
) -> list[Finding]:
    """Report function names that open with no known verb.

    Args:
        functions: The definitions to read.
        verbs: Verb to family.

    Returns:
        One observation per verbless name.
    """
    return [
        Finding(
            "L002",
            f'"{definition.name}" does not start with a known verb',
            definition.module,
            definition.lineno,
            definition.qualname,
        )
        for definition in functions
        if _leading_verb(definition, verbs) is None
    ]


def _docstring_disagreement(
    functions: Iterable[Definition], verbs: Mapping[str, str]
) -> list[Finding]:
    """Report names and docstrings that describe different actions.

    A docstring opening on a return verb announces the signature, not the
    operation, and never counts as a disagreement.

    Args:
        functions: The definitions to read.
        verbs: Verb to family.

    Returns:
        One observation per disagreement.
    """
    findings: list[Finding] = []
    for definition in functions:
        name_verb = _leading_verb(definition, verbs)
        doc_verb = _docstring_verb(definition, verbs)
        if not name_verb or not doc_verb:
            continue
        if verbs[doc_verb] == ANNOUNCES_A_RETURN:
            continue
        if verbs[name_verb] != verbs[doc_verb]:
            findings.append(
                Finding(
                    "L003",
                    f'the name says "{name_verb}", the docstring says "{doc_verb}"',
                    definition.module,
                    definition.lineno,
                    definition.qualname,
                )
            )
    return findings


def _abbreviations(
    definitions: Iterable[Definition],
    table: Mapping[str, list[str]] | None = None,
) -> list[Finding]:
    """Report abbreviations whose full word is used elsewhere.

    Args:
        definitions: The definitions to read.
        table: Abbreviation to full words. Defaults to the shipped table.

    Returns:
        One observation per abbreviation shadowing a spelled-out word.
    """
    table = table if table is not None else load_abbreviations()
    sites: dict[str, Definition] = {}
    present: set[str] = set()
    for definition in definitions:
        for word in split_chosen_words(definition.name):
            present.add(word)
            sites.setdefault(word, definition)

    findings: list[Finding] = []
    for short in sorted(present & set(table)):
        for long_word in table[short]:
            if long_word in present:
                definition = sites[short]
                findings.append(
                    Finding(
                        "L004",
                        f'"{short}" abbreviates "{long_word}", spelled out elsewhere',
                        definition.module,
                        definition.lineno,
                        definition.qualname,
                    )
                )
    return findings


def _polysemy(
    functions: Iterable[Definition],
    verbs: Mapping[str, str],
    imports: Mapping[str, dict[str, str]],
    project_roots: Collection[str],
) -> list[Finding]:
    """Report verbs used over unrelated third-party libraries.

    Args:
        functions: The definitions to read.
        verbs: Verb to family.
        imports: Module name to its imports.
        project_roots: Top-level packages belonging to the project.

    Returns:
        One observation per verb spanning disjoint worlds.
    """
    worlds: dict[str, list[tuple[Definition, set[str]]]] = defaultdict(list)
    for definition in functions:
        verb = _leading_verb(definition, verbs)
        if not verb:
            continue
        roots = _third_party_roots(
            definition, imports.get(definition.module, {}), project_roots
        )
        if roots:
            worlds[verb].append((definition, roots))

    findings: list[Finding] = []
    for verb, entries in worlds.items():
        for index, (definition, roots) in enumerate(entries):
            rest = entries[index + 1 :]
            others: set[str] = (
                set().union(*(other for _, other in rest)) if rest else set()
            )
            if others and not (roots & others):
                findings.append(
                    Finding(
                        "L005",
                        f'"{verb}" spans two worlds: '
                        f"{', '.join(sorted(roots))} on one side, "
                        f"{', '.join(sorted(others))} on the other",
                        definition.module,
                        definition.lineno,
                        definition.qualname,
                    )
                )
                break
    return findings
