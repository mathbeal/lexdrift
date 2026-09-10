from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

from lexdrift.cli import main
from lexdrift.collector import collect_source
from lexdrift.drift import compare
from lexdrift.project import glossary, inspect
from lexdrift.rename import rename
from lexdrift.report import as_json

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def make(tmp_path: Path, files: dict[str, str]) -> str:
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return str(tmp_path)


# --- collector ---------------------------------------------------------------


def test_a_call_on_a_subscript_has_no_dotted_name() -> None:
    module = collect_source("def go():\n    return handlers['x']()\n", module="m")
    assert module.definitions[0].calls == []


def test_async_functions_are_collected() -> None:
    module = collect_source("async def fetch():\n    pass\n", module="m")
    assert module.definitions[0].name == "fetch"


# --- project -----------------------------------------------------------------


def test_a_file_that_does_not_parse_is_recorded_as_unreadable(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/broken.py": "def (:\n"})
    assert inspect(root).unreadable


def test_a_class_name_feeds_the_nouns(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "class UserAccount:\n    pass\n"})
    lexicon = glossary(inspect(root))
    assert lexicon["nouns"]["account"] == 1


def test_a_name_made_only_of_underscores_is_skipped(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "def _():\n    pass\n"})
    assert glossary(inspect(root))["nouns"] == {}


# --- drift -------------------------------------------------------------------


def test_an_abbreviation_without_its_full_word_is_silent(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "def read_cfg_file():\n    pass\n"})
    assert not [f for f in compare(inspect(root)) if f.rule == "D002"]


# --- report ------------------------------------------------------------------


def test_json_report_carries_rule_path_and_line(tmp_path: Path) -> None:
    root = make(
        tmp_path,
        {"app/m.py": "def get_a():\n    pass\n\n\ndef fetch_b():\n    pass\n"},
    )
    project = inspect(root)
    payload = json.loads(as_json(project, compare(project)))
    assert payload[0]["path"] == "app/m.py"
    assert payload[0]["rule"] == "D001"


# --- rename ------------------------------------------------------------------


def test_rename_skips_a_file_that_does_not_parse(tmp_path: Path) -> None:
    root = make(
        tmp_path,
        {"app/ok.py": "def old_one():\n    pass\n", "app/broken.py": "def (:\n"},
    )
    assert rename(root, "old_one", "new_one").renamed == 1


def test_rename_skips_an_undecodable_side_file(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "def old_one():\n    pass\n"})
    (tmp_path / "notes.md").write_bytes(b"\xff\xfe binaire")
    assert rename(root, "old_one", "new_one").renamed == 1


def test_rename_refuses_a_collision_inside_a_class(tmp_path: Path) -> None:
    source = (
        "class A:\n"
        "    def old_one(self):\n"
        "        pass\n"
        "\n"
        "    def new_one(self):\n"
        "        pass\n"
    )
    root = make(tmp_path, {"app/m.py": source})
    assert rename(root, "old_one", "new_one").refusal is not None


def test_rename_renames_an_import_module(tmp_path: Path) -> None:
    root = make(
        tmp_path,
        {"app/m.py": "import old_one\n", "old_one.py": "def go():\n    pass\n"},
    )
    rename(root, "old_one", "new_one")
    assert "import new_one" in (tmp_path / "app" / "m.py").read_text(encoding="utf-8")


# --- ligne de commande -------------------------------------------------------


def test_rename_refuses_a_modified_git_tree(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "def old_one():\n    pass\n"})
    subprocess.run(["git", "init", "-q", root], check=True)
    assert main(["rename", "old_one", "new_one", root]) == 1


def test_rename_prints_what_it_refused_to_touch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make(
        tmp_path,
        {
            "app/m.py": "class A:\n    def go(self, c):\n        return c.old_one()\n",
            "tpl/a.html": "{{ old_one }}\n",
        },
    )
    assert main(["rename", "old_one", "new_one", root]) == 0
    printed = capsys.readouterr().out
    assert "left untouched" in printed
    assert "non-Python" in printed


def test_check_can_report_as_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make(
        tmp_path,
        {"app/m.py": "def get_a():\n    pass\n\n\ndef fetch_b():\n    pass\n"},
    )
    assert main(["check", root, "--format", "json"]) == 1
    assert json.loads(capsys.readouterr().out)[0]["rule"] == "D001"


def test_dump_prints_observations_when_the_corpus_has_some(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make(
        tmp_path,
        {"app/m.py": "def get_a():\n    pass\n\n\ndef fetch_b():\n    pass\n"},
    )
    main(["dump", root])
    assert "observations" in capsys.readouterr().out


def test_main_reads_sys_argv_when_given_nothing(
    tmp_path: Path, monkeypatch: object
) -> None:
    root = make(tmp_path, {"app/m.py": "def get_a():\n    pass\n"})
    monkeypatch.setattr(sys, "argv", ["lexdrift", root])  # type: ignore[attr-defined]
    assert main() == 0


def test_rename_handles_an_async_function(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "async def old_one():\n    pass\n"})
    assert rename(root, "old_one", "new_one").renamed == 1


def test_rename_refuses_when_the_new_name_is_already_referenced(
    tmp_path: Path,
) -> None:
    source = "def old_one():\n    pass\n\n\ndef go():\n    return new_one()\n"
    root = make(tmp_path, {"app/m.py": source})
    assert rename(root, "old_one", "new_one").refusal is not None


def test_rename_ignores_a_file_type_it_does_not_read(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "def old_one():\n    pass\n"})
    (tmp_path / "image.png").write_bytes(b"\x89PNG old_one")
    assert not rename(root, "old_one", "new_one").warnings


def test_rename_proceeds_on_a_modified_tree_when_forced(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "def old_one():\n    pass\n"})
    subprocess.run(["git", "init", "-q", root], check=True)
    assert main(["rename", "old_one", "new_one", root, "--force"]) == 0


def test_dump_says_nothing_when_there_is_nothing_to_observe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make(tmp_path, {"app/m.py": "def get_a():\n    pass\n"})
    main(["dump", root])
    assert "observations" not in capsys.readouterr().out


def test_a_root_level_init_has_no_module_name(tmp_path: Path) -> None:
    root = make(tmp_path, {"__init__.py": "", "app/m.py": "def get_a():\n    pass\n"})
    assert "" not in inspect(root).project_roots


def test_a_name_led_by_an_unknown_word_feeds_the_nouns(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "def zzz_thing():\n    pass\n"})
    assert glossary(inspect(root))["nouns"]["zzz"] == 1


def test_an_unknown_verb_is_ignored_by_the_drift(tmp_path: Path) -> None:
    root = make(
        tmp_path,
        {"app/m.py": "def zzz_thing():\n    pass\n\n\ndef get_a():\n    pass\n"},
    )
    assert not [f for f in compare(inspect(root)) if f.rule == "D001"]


def test_a_call_to_a_local_name_is_not_a_third_party_world(tmp_path: Path) -> None:
    source = "def helper():\n    pass\n\n\ndef get_a():\n    return helper()\n"
    root = make(tmp_path, {"app/m.py": source})
    from lexdrift.project import findings as measure

    assert not [f for f in measure(inspect(root)) if f.rule == "L005"]


def test_the_module_entry_point_runs(tmp_path: Path) -> None:
    root = make(tmp_path, {"app/m.py": "def get_a():\n    pass\n"})
    done = subprocess.run(
        [sys.executable, "-m", "lexdrift", "dump", root],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0
    assert "names chosen" in done.stdout


def test_an_abbreviation_already_in_the_baseline_is_accepted(tmp_path: Path) -> None:
    source = "def read_user():\n    pass\n\n\ndef read_usr_file():\n    pass\n"
    root = make(tmp_path, {"app/m.py": source})
    project = inspect(root)
    baseline = glossary(project)
    assert not [f for f in compare(project, baseline) if f.rule == "D002"]


def test_rename_ignores_an_import_of_something_else(tmp_path: Path) -> None:
    source = "from os import path\n\n\ndef old_one():\n    pass\n"
    root = make(tmp_path, {"app/m.py": source})
    result = rename(root, "old_one", "new_one")
    assert result.renamed == 1
    assert "from os import path" in (tmp_path / "app" / "m.py").read_text(
        encoding="utf-8"
    )


def test_rename_reads_a_side_file_without_finding_anything(tmp_path: Path) -> None:
    root = make(
        tmp_path,
        {"app/m.py": "def old_one():\n    pass\n", "notes.md": "rien à voir\n"},
    )
    assert rename(root, "old_one", "new_one").warnings == []
