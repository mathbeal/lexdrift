from __future__ import annotations

from typing import TYPE_CHECKING

from lexdrift.project import build_lexicon, discover, inspect

if TYPE_CHECKING:
    from pathlib import Path


def build(tmp_path: Path, files: object) -> None:
    for relative, content in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


def test_discover_finds_python_files(tmp_path: Path) -> None:
    root = build(tmp_path, {"app/models.py": "", "app/views.py": ""})
    assert len(discover(root)) == 2


def test_discover_skips_vendored_directories(tmp_path: Path) -> None:
    root = build(
        tmp_path,
        {
            "app/models.py": "",
            ".venv/lib/site-packages/django/db.py": "",
            "node_modules/x/y.py": "",
            "build/lib/copy.py": "",
        },
    )
    assert [p.name for p in discover(root)] == ["models.py"]


def test_inspect_infers_project_roots_from_top_level_packages(tmp_path: Path) -> None:
    root = build(tmp_path, {"app/models.py": "import requests\n"})
    assert "app" in inspect(root).project_roots


def test_the_lexicon_counts_only_the_projects_own_verbs(tmp_path: Path) -> None:
    root = build(
        tmp_path,
        {
            "app/models.py": (
                "from django.db import models\n"
                "class Account(models.Model):\n"
                "    def save_account(self):\n"
                "        pass\n"
                "def build_report():\n"
                "    pass\n"
            )
        },
    )
    result = build_lexicon(inspect(root))
    assert result["verbs"]["build"] == 1
    assert "save" not in result["verbs"]
    assert result["imposed"] == 1
