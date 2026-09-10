from __future__ import annotations

from typing import TYPE_CHECKING

from lexdrift.collector import collect_source
from lexdrift.project import discover
from lexdrift.rules import measure

if TYPE_CHECKING:
    from pathlib import Path


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
    assert [p for p in discover(tmp_path) if "nosync" in p] == []


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
