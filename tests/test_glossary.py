from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from lexdrift.project import Narrowing, filter_lexicon, glossary, inspect

if TYPE_CHECKING:
    from pathlib import Path


def lexicon_of(tmp_path: Path, source: str) -> dict[str, object]:
    (tmp_path / "mod.py").write_text(source, encoding="utf-8")
    return glossary(inspect(tmp_path))


def test_a_function_word_is_not_counted_as_a_noun(tmp_path: Path) -> None:
    nouns = lexicon_of(tmp_path, "def as_json():\n    pass\n")["nouns"]
    assert "json" in nouns
    assert "as" not in nouns


def test_a_function_word_alone_still_counts(tmp_path: Path) -> None:
    nouns = lexicon_of(tmp_path, "class As:\n    pass\n")["nouns"]
    assert nouns == {"as": 1}


def test_a_declared_compound_counts_as_one_noun(tmp_path: Path) -> None:
    nouns = lexicon_of(tmp_path, "class ThirdPartyRoot:\n    pass\n")["nouns"]
    assert nouns == {"third party": 1, "root": 1}


def test_an_undeclared_pair_stays_two_nouns(tmp_path: Path) -> None:
    nouns = lexicon_of(tmp_path, "class PurpleRoot:\n    pass\n")["nouns"]
    assert nouns == {"purple": 1, "root": 1}


SPREAD = {
    "verbs": {"load": 3, "dump": 2, "split": 1},
    "nouns": {"word": 4, "family": 2, "hapax": 1},
    "families": {"obtain": {"load": 3}, "export": {"dump": 2}, "split": {"split": 1}},
    "own": 6,
    "imposed": 0,
    "imposed_by_reason": {},
}


def test_most_common_keeps_the_head_of_each_list() -> None:
    kept = filter_lexicon(SPREAD, Narrowing(most_common=2))
    assert kept["verbs"] == {"load": 3, "dump": 2}
    assert kept["nouns"] == {"word": 4, "family": 2}


def test_least_common_keeps_the_tail_where_drift_hides() -> None:
    kept = filter_lexicon(SPREAD, Narrowing(least_common=2))
    assert kept["verbs"] == {"split": 1, "dump": 2}
    assert kept["nouns"] == {"hapax": 1, "family": 2}


def test_min_count_drops_what_is_rarer() -> None:
    assert filter_lexicon(SPREAD, Narrowing(min_count=2))["nouns"] == {
        "word": 4,
        "family": 2,
    }


def test_max_count_keeps_only_the_rare() -> None:
    assert filter_lexicon(SPREAD, Narrowing(max_count=1))["nouns"] == {"hapax": 1}


def test_kind_verbs_empties_the_nouns() -> None:
    kept = filter_lexicon(SPREAD, Narrowing(kind="verbs"))
    assert kept["nouns"] == {}
    assert kept["verbs"] == SPREAD["verbs"]


def test_kind_nouns_empties_the_verbs_and_their_families() -> None:
    kept = filter_lexicon(SPREAD, Narrowing(kind="nouns"))
    assert kept["verbs"] == {}
    assert kept["families"] == {}


def test_families_follow_the_verbs_that_survive() -> None:
    assert filter_lexicon(SPREAD, Narrowing(most_common=1))["families"] == {
        "obtain": {"load": 3}
    }


def test_the_corpus_totals_are_never_filtered() -> None:
    kept = filter_lexicon(SPREAD, Narrowing(most_common=1))
    assert kept["own"] == SPREAD["own"]
    assert kept["imposed"] == SPREAD["imposed"]


def test_no_filter_returns_the_lexicon_unchanged() -> None:
    assert filter_lexicon(SPREAD) == SPREAD


def test_most_and_least_common_together_are_refused() -> None:
    with pytest.raises(ValueError, match="most_common"):
        Narrowing(most_common=1, least_common=1)


def test_a_narrowing_that_asks_for_nothing_does_not_narrow() -> None:
    assert Narrowing().narrows is False
    assert Narrowing(kind="verbs").narrows is True
