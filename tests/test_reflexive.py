"""lexdrift on lexdrift.

A tool that names concepts must name its own. This runs in the unit suite,
not only in CI, so that a name introduced this minute fails this minute.
"""

from __future__ import annotations

from pathlib import Path

from lexdrift.drift import compare
from lexdrift.lexicon import FUNCTION_WORDS
from lexdrift.project import glossary, inspect

SOURCE = Path(__file__).resolve().parent.parent / "lexdrift"


def test_lexdrift_has_not_drifted_on_its_own_source() -> None:
    assert compare(inspect(SOURCE)) == []


def test_lexdrift_names_one_verb_per_family() -> None:
    families = glossary(inspect(SOURCE))["families"]
    several = {f: verbs for f, verbs in families.items() if len(verbs) > 1}
    assert several == {}


def test_lexdrift_glossary_carries_no_function_word() -> None:
    nouns = set(glossary(inspect(SOURCE))["nouns"])
    assert nouns & FUNCTION_WORDS == set()
