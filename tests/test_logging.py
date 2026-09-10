"""Diagnostics go through the logger, the product goes to stdout."""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from lexdrift.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

DRIFTING = "def get_a():\n    pass\n\n\ndef fetch_b():\n    pass\n"


def make(tmp_path: Path, source: str) -> str:
    target = tmp_path / "app" / "models.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return str(tmp_path)


def test_a_missing_baseline_is_logged_not_printed(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with caplog.at_level(logging.INFO, logger="lexdrift"):
        main(["check", make(tmp_path, DRIFTING)])
    assert "no baseline" in caplog.text
    assert "no baseline" not in capsys.readouterr().out


def test_being_outside_a_git_repository_is_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = make(tmp_path, "def old_one():\n    pass\n")
    with caplog.at_level(logging.WARNING, logger="lexdrift"):
        main(["rename", "old_one", "new_one", root])
    assert caplog.records[0].levelno == logging.WARNING
    assert "cannot be undone" in caplog.text


def test_a_modified_git_tree_is_an_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = make(tmp_path, "def old_one():\n    pass\n")
    subprocess.run(["git", "init", "-q", root], check=True)
    with caplog.at_level(logging.ERROR, logger="lexdrift"):
        assert main(["rename", "old_one", "new_one", root]) == 1
    assert "modified git tree" in caplog.text


def test_a_refused_rename_is_an_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    source = "def old_one():\n    pass\n\n\ndef new_one():\n    pass\n"
    root = make(tmp_path, source)
    with caplog.at_level(logging.ERROR, logger="lexdrift"):
        assert main(["rename", "old_one", "new_one", root]) == 1
    assert "already exists in the same scope" in caplog.text


def test_the_product_never_goes_through_the_logger(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with caplog.at_level(logging.DEBUG, logger="lexdrift"):
        main(["dump", make(tmp_path, DRIFTING), "--format", "tsv"])
    printed = capsys.readouterr().out
    assert "\t" in printed
    assert caplog.text == ""
