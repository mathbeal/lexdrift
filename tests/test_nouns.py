from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from lexdrift.config import load_config
from lexdrift.drift import compare
from lexdrift.project import findings, inspect

if TYPE_CHECKING:
    from pathlib import Path

DECLARED = '[nouns]\nuser = ["user", "account", "customer"]\n'


def project_with(tmp_path: Path, source: str, config: str = DECLARED) -> object:
    (tmp_path / "mod.py").write_text(source, encoding="utf-8")
    if config:
        (tmp_path / "lexdrift.toml").write_text(config, encoding="utf-8")
    return inspect(tmp_path)


def rules_of(project: object) -> set[str]:
    return {f.rule for f in findings(project)}


def test_a_declared_noun_family_named_twice_is_reported(tmp_path: Path) -> None:
    source = "def load_user():\n    pass\n\ndef edit_account():\n    pass\n"
    found = [f for f in findings(project_with(tmp_path, source)) if f.rule == "L006"]
    assert len(found) == 1
    assert "account" in found[0].message
    assert "user" in found[0].message


def test_a_declared_noun_family_named_once_is_silent(tmp_path: Path) -> None:
    source = "def load_user():\n    pass\n\ndef edit_user():\n    pass\n"
    assert "L006" not in rules_of(project_with(tmp_path, source))


def test_an_undeclared_noun_is_never_reported(tmp_path: Path) -> None:
    source = "def load_widget():\n    pass\n\ndef edit_gadget():\n    pass\n"
    assert "L006" not in rules_of(project_with(tmp_path, source))


def test_without_a_config_no_noun_is_declared(tmp_path: Path) -> None:
    source = "def load_user():\n    pass\n\ndef edit_account():\n    pass\n"
    assert "L006" not in rules_of(project_with(tmp_path, source, config=""))


def test_a_class_name_carries_its_nouns(tmp_path: Path) -> None:
    source = "class User:\n    pass\n\nclass Account:\n    pass\n"
    assert "L006" in rules_of(project_with(tmp_path, source))


def test_a_new_noun_for_a_declared_idea_is_drift(tmp_path: Path) -> None:
    source = (
        "def load_user():\n    pass\n\ndef edit_user():\n    pass\n\n"
        "def save_account():\n    pass\n"
    )
    project = project_with(tmp_path, source)
    baseline = {"nouns": {"user": 2}, "verbs": {}, "families": {}}
    found = [f for f in compare(project, baseline) if f.rule == "D004"]
    assert len(found) == 1
    assert '"account" is new' in found[0].message


def test_a_noun_already_in_the_baseline_is_not_drift(tmp_path: Path) -> None:
    source = "def load_user():\n    pass\n\ndef edit_account():\n    pass\n"
    project = project_with(tmp_path, source)
    baseline = {"nouns": {"user": 1, "account": 1}, "verbs": {}, "families": {}}
    assert [f for f in compare(project, baseline) if f.rule == "D004"] == []


def test_without_a_baseline_the_most_used_noun_is_the_established_one(
    tmp_path: Path,
) -> None:
    source = (
        "def load_user():\n    pass\n\ndef edit_user():\n    pass\n\n"
        "def save_customer():\n    pass\n"
    )
    found = [f for f in compare(project_with(tmp_path, source)) if f.rule == "D004"]
    assert len(found) == 1
    assert '"customer" is new' in found[0].message
    assert "user" in found[0].message


def test_no_config_file_declares_nothing(tmp_path: Path) -> None:
    assert load_config(str(tmp_path)) == {}


def test_the_nouns_table_is_read(tmp_path: Path) -> None:
    (tmp_path / "lexdrift.toml").write_text(DECLARED, encoding="utf-8")
    assert load_config(str(tmp_path)) == {"user": ["user", "account", "customer"]}


def test_a_config_without_a_nouns_table_declares_nothing(tmp_path: Path) -> None:
    (tmp_path / "lexdrift.toml").write_text("# nothing here\n", encoding="utf-8")
    assert load_config(str(tmp_path)) == {}


def test_a_family_that_is_not_a_list_of_words_is_refused(tmp_path: Path) -> None:
    (tmp_path / "lexdrift.toml").write_text(
        '[nouns]\nuser = "account"\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="user"):
        load_config(str(tmp_path))


def test_a_declared_noun_used_once_is_not_drift(tmp_path: Path) -> None:
    source = "def load_user():\n    pass\n\ndef save_widget():\n    pass\n"
    project = project_with(tmp_path, source)
    assert [f for f in compare(project) if f.rule == "D004"] == []


PYPROJECT = '[tool.lexdrift.nouns]\nuser = ["user", "account"]\n'


def test_the_pyproject_table_is_read(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    assert load_config(str(tmp_path)) == {"user": ["user", "account"]}


def test_a_pyproject_without_a_lexdrift_table_declares_nothing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    assert load_config(str(tmp_path)) == {}


def test_a_dedicated_file_wins_over_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "lexdrift.toml").write_text(DECLARED, encoding="utf-8")
    assert load_config(str(tmp_path)) == {"user": ["user", "account", "customer"]}


def test_the_config_is_found_from_a_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "lexdrift.toml").write_text(DECLARED, encoding="utf-8")
    package = tmp_path / "src" / "app"
    package.mkdir(parents=True)
    assert load_config(str(package)) == {"user": ["user", "account", "customer"]}


def test_the_search_stops_at_the_repository_boundary(tmp_path: Path) -> None:
    (tmp_path / "lexdrift.toml").write_text(DECLARED, encoding="utf-8")
    repository = tmp_path / "other"
    (repository / ".git").mkdir(parents=True)
    package = repository / "app"
    package.mkdir()
    assert load_config(str(package)) == {}


def test_a_declared_family_applies_from_the_root_of_the_repository(
    tmp_path: Path,
) -> None:
    (tmp_path / "lexdrift.toml").write_text(DECLARED, encoding="utf-8")
    package = tmp_path / "app"
    package.mkdir()
    (package / "mod.py").write_text(
        "def load_user():\n    pass\n\ndef edit_account():\n    pass\n", encoding="utf-8"
    )
    assert "L006" in {f.rule for f in findings(inspect(package))}
