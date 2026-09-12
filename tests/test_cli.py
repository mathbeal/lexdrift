from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from lexdrift.cli import main

if TYPE_CHECKING:
    from pathlib import Path

DRIFTING = "def get_user():\n    pass\n\ndef fetch_account():\n    pass\n"
CLEAN = "def get_user():\n    pass\n\ndef get_account():\n    pass\n"


def make(tmp_path: Path, source: object) -> None:
    target = tmp_path / "app" / "models.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return str(tmp_path)


def test_check_exits_1_on_drift(tmp_path: Path) -> None:
    assert main(["check", make(tmp_path, DRIFTING)]) == 1


def test_check_exits_0_on_a_clean_lexicon(tmp_path: Path) -> None:
    assert main(["check", make(tmp_path, CLEAN)]) == 0


def test_check_is_the_implicit_subcommand(tmp_path: Path) -> None:
    assert main([make(tmp_path, DRIFTING)]) == 1


def test_dump_never_fails(tmp_path: Path) -> None:
    assert main(["dump", make(tmp_path, DRIFTING)]) == 0


def test_dump_tsv_lists_words_by_decreasing_frequency(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = (
        "def get_user_name():\n    pass\n"
        "def get_user_id():\n    pass\n"
        "def build_report():\n    pass\n"
    )
    main(["dump", make(tmp_path, source), "--format", "tsv"])
    counts = [int(line.split("\t")[0]) for line in capsys.readouterr().out.splitlines()]
    assert counts == sorted(counts, reverse=True)


def test_dump_tsv_carries_word_kind_and_family(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["dump", make(tmp_path, CLEAN), "--format", "tsv"])
    rows = [line.split("\t") for line in capsys.readouterr().out.splitlines()]
    assert ["2", "get", "verb", "obtain"] in rows


def test_dump_json_is_accepted_back_as_a_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make(tmp_path, DRIFTING)
    main(["dump", root, "--format", "json"])
    reference = tmp_path / "lexdrift.lock"
    reference.write_text(capsys.readouterr().out, encoding="utf-8")
    assert main(["check", root, "--baseline", str(reference)]) == 0


def test_check_reports_sarif_when_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["check", make(tmp_path, DRIFTING), "--format", "sarif"])
    assert json.loads(capsys.readouterr().out)["version"] == "2.1.0"


RENAMEABLE = "def fetch_account():\n    pass\n\ndef main():\n    return fetch_account()\n"


def test_rename_rewrites_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make(tmp_path, RENAMEABLE)
    assert main(["rename", "fetch_account", "get_account", root]) == 0
    assert "def get_account():" in (tmp_path / "app" / "models.py").read_text()


def test_rename_dry_run_leaves_the_file_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make(tmp_path, RENAMEABLE)
    assert main(["rename", "fetch_account", "get_account", root, "--dry-run"]) == 0
    assert "def fetch_account():" in (tmp_path / "app" / "models.py").read_text()


def test_rename_refuses_a_collision_and_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = "def fetch_account():\n    pass\n\ndef get_account():\n    pass\n"
    root = make(tmp_path, source)
    assert main(["rename", "fetch_account", "get_account", root]) == 1


def test_version_prints_the_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    from lexdrift import __version__

    with pytest.raises(SystemExit) as exit_code:
        main(["--version"])
    assert exit_code.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_dump_most_common_narrows_every_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["dump", "lexdrift", "--format", "tsv", "--most-common", "3"])
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 6  # 3 verbs and 3 nouns


def test_dump_max_count_one_lists_the_words_used_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["dump", "lexdrift", "--format", "tsv", "--max-count", "1"])
    counts = {
        line.split("\t")[0] for line in capsys.readouterr().out.strip().splitlines()
    }
    assert counts == {"1"}


def test_dump_kind_verbs_prints_no_noun(capsys: pytest.CaptureFixture[str]) -> None:
    main(["dump", "lexdrift", "--kind", "verbs"])
    out = capsys.readouterr().out
    assert "verbs, by family" in out
    assert "\n  \n" not in out


def test_dump_unnarrowed_says_how_many_nouns_it_shows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["dump", "lexdrift"])
    assert "most used nouns, 20 shown" in capsys.readouterr().out


def test_dump_narrowed_shows_every_noun_it_kept(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["dump", "lexdrift", "--least-common", "2"])
    out = capsys.readouterr().out
    assert "\nnouns\n" in out
    assert "shown" not in out


def test_dump_kind_nouns_prints_no_family(capsys: pytest.CaptureFixture[str]) -> None:
    main(["dump", "lexdrift", "--kind", "nouns"])
    assert "verbs, by family" not in capsys.readouterr().out


def test_dump_says_how_to_declare_noun_families(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A project of its own, because lexdrift now declares its families and
    # would not print the hint: a test that reads the repository it lives in
    # asserts on today's repository, not on the behaviour.
    (tmp_path / "mod.py").write_text("def load_user():\n    pass\n", encoding="utf-8")
    main(["dump", str(tmp_path)])
    assert "[tool.lexdrift.nouns]" in capsys.readouterr().out


def test_dump_lists_the_declared_noun_families(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "mod.py").write_text("def load_user():\n    pass\n", encoding="utf-8")
    (tmp_path / "lexdrift.toml").write_text(
        '[nouns]\nuser = ["customer"]\n', encoding="utf-8"
    )
    main(["dump", str(tmp_path)])
    out = capsys.readouterr().out
    assert "1 noun families declared" in out
    assert "user       customer" in out


def test_a_broken_declaration_is_reported_not_raised(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "mod.py").write_text("def load_user():\n    pass\n", encoding="utf-8")
    (tmp_path / "lexdrift.toml").write_text("[nouns]\nuser = 3\n", encoding="utf-8")
    assert main(["check", str(tmp_path)]) == 1
    assert "list of words" in caplog.text


def test_unreadable_toml_is_reported_not_raised(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "mod.py").write_text("def load_user():\n    pass\n", encoding="utf-8")
    (tmp_path / "lexdrift.toml").write_text("[nouns\n", encoding="utf-8")
    assert main(["check", str(tmp_path)]) == 1
    assert caplog.text
