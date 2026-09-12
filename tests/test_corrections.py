from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lexdrift.collector import collect_source
from lexdrift.project import discover
from lexdrift.rules import measure


def rules_fired(source: object) -> None:
    modules = [collect_source(source, module="app.mod")]
    return {f.rule for f in measure(modules, project_roots={"app"})}


def test_discover_skips_any_directory_holding_a_pyvenv_cfg(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "models.py").write_text("", encoding="utf-8")
    weird = tmp_path / ".venv.nosync"
    (weird / "bin").mkdir(parents=True)
    (weird / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    (weird / "bin" / "dumppdf.py").write_text("", encoding="utf-8")
    assert [p for p in discover(tmp_path) if "nosync" in str(p)] == []


def test_L003_ignores_a_docstring_that_merely_announces_a_return() -> None:
    source = 'def get_user():\n    """Retourne l\'utilisateur."""\n'
    assert "L003" not in rules_fired(source)


def test_L003_still_fires_on_a_real_disagreement() -> None:
    source = 'def get_user():\n    """Supprime l\'utilisateur."""\n'
    assert "L003" in rules_fired(source)


def test_L004_uses_a_curated_table_not_a_subsequence_guess() -> None:
    noise = "def read_text():\n    pass\n\ndef read_context():\n    pass\n"
    assert "L004" not in rules_fired(noise)


def test_L004_reports_a_known_abbreviation_whose_word_is_used() -> None:
    source = "def read_usr_file():\n    pass\n\ndef read_user_name():\n    pass\n"
    assert "L004" in rules_fired(source)


def test_common_verbs_are_known(tmp_path: Path) -> None:
    for verb in ("guess", "group", "extract", "merge", "split", "compare"):
        source = f"def {verb}_things():\n    pass\n"
        assert "L002" not in rules_fired(source), verb


def test_a_test_function_contributes_its_own_words(tmp_path: Path) -> None:
    from lexdrift.project import build_lexicon, inspect

    root = tmp_path / "app"
    root.mkdir()
    (root / "t.py").write_text("def test_fetch_account():\n    pass\n", encoding="utf-8")
    lexicon = build_lexicon(inspect(tmp_path))
    assert lexicon["verbs"]["fetch"] == 1
    assert "test" not in lexicon["nouns"]


def test_the_test_prefix_never_counts_as_a_verb(tmp_path: Path) -> None:
    from lexdrift.split import split_chosen_words

    assert split_chosen_words("test_fetch_account") == ["fetch", "account"]
    assert split_chosen_words("testament_parser") == ["testament", "parser"]
    assert split_chosen_words("fetch_account") == ["fetch", "account"]
    # A convention word alone is the whole name, not a prefix to drop: `test`
    # names something, and returning [] here would erase it from the lexicon.
    assert split_chosen_words("test") == ["test"]


def test_the_lexicon_says_why_names_were_imposed(tmp_path: Path) -> None:
    from lexdrift.project import build_lexicon, inspect

    root = tmp_path / "app"
    root.mkdir()
    (root / "m.py").write_text(
        "class A:\n    def __init__(self):\n        pass\n", encoding="utf-8"
    )
    reasons = build_lexicon(inspect(tmp_path))["imposed_by_reason"]
    assert reasons == {"language special method": 1}


def test_dump_prints_the_reasons(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from lexdrift.cli import main

    root = tmp_path / "app"
    root.mkdir()
    (root / "m.py").write_text(
        "class A:\n    def __init__(self):\n        pass\n", encoding="utf-8"
    )
    main(["dump", str(tmp_path)])
    assert "language special method" in capsys.readouterr().out


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="tomllib landed in 3.11; CI covers it there"
)
def test_the_two_declarations_of_dev_dependencies_agree() -> None:
    """Pip reads the extra, uv reads the group. They must not drift."""
    import tomllib

    root = Path(__file__).resolve().parent.parent
    data = tomllib.loads(root.joinpath("pyproject.toml").read_text(encoding="utf-8"))
    extra = data["project"]["optional-dependencies"]["dev"]
    group = data["dependency-groups"]["dev"]
    assert extra == group
