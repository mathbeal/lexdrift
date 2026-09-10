from __future__ import annotations

import json
from typing import TYPE_CHECKING

from lexdrift.drift import compare
from lexdrift.project import inspect
from lexdrift.report import as_sarif, as_text

if TYPE_CHECKING:
    from pathlib import Path

DRIFTING = (
    "def get_user():\n    pass\n"
    "def get_account():\n    pass\n"
    "def fetch_order():\n    pass\n"
)


def prepared(tmp_path: Path) -> None:
    target = tmp_path / "app" / "models.py"
    target.parent.mkdir(parents=True)
    target.write_text(DRIFTING, encoding="utf-8")
    project = inspect(tmp_path)
    return project, compare(project)


def test_text_line_gives_path_line_and_rule(tmp_path: Path) -> None:
    project, found = prepared(tmp_path)
    assert as_text(project, found).splitlines()[0].startswith("app/models.py:5: D001 ")


def test_sarif_is_version_2_1_0(tmp_path: Path) -> None:
    project, found = prepared(tmp_path)
    assert json.loads(as_sarif(project, found))["version"] == "2.1.0"


def test_sarif_result_points_at_the_offending_definition(tmp_path: Path) -> None:
    project, found = prepared(tmp_path)
    result = json.loads(as_sarif(project, found))["runs"][0]["results"][0]
    location = result["locations"][0]["physicalLocation"]
    assert result["ruleId"] == "D001"
    assert location["artifactLocation"]["uri"] == "app/models.py"
    assert location["region"]["startLine"] == 5


def test_sarif_declares_every_rule_in_the_driver(tmp_path: Path) -> None:
    project, found = prepared(tmp_path)
    driver = json.loads(as_sarif(project, found))["runs"][0]["tool"]["driver"]
    assert {rule["id"] for rule in driver["rules"]} == {"D001", "D002", "D003", "D004"}
