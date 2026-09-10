"""lexdrift on lexdrift.

A tool that names concepts must name its own. This runs in the unit suite,
not only in CI, so that a name introduced this minute fails this minute.
"""

from __future__ import annotations

import re
from pathlib import Path

from lexdrift.config import load_config
from lexdrift.drift import compare
from lexdrift.lexicon import FUNCTION_WORDS
from lexdrift.project import glossary, inspect

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "lexdrift"


def test_lexdrift_has_not_drifted_on_its_own_source() -> None:
    assert compare(inspect(SOURCE)) == []


def test_lexdrift_names_one_verb_per_family() -> None:
    families = glossary(inspect(SOURCE))["families"]
    several = {f: verbs for f, verbs in families.items() if len(verbs) > 1}
    assert several == {}


def test_lexdrift_glossary_carries_no_function_word() -> None:
    nouns = set(glossary(inspect(SOURCE))["nouns"])
    assert nouns & FUNCTION_WORDS == set()


def test_every_declaration_shown_in_the_readme_is_accepted(tmp_path: Path) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```toml\n(.*?)```", readme, re.DOTALL)
    assert blocks, "the README no longer shows a declaration"
    for index, block in enumerate(blocks):
        directory = tmp_path / str(index)
        directory.mkdir()
        (directory / "pyproject.toml").write_text(block, encoding="utf-8")
        assert load_config(str(directory)), f"block {index + 1} declares nothing"
