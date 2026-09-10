from __future__ import annotations

from typing import TYPE_CHECKING

from lexdrift.rename import rename

if TYPE_CHECKING:
    from pathlib import Path

MODULE = '''# en-tête conservé
import os

from .helpers import fetch_account   # import nommé


def fetch_account(uid):
    """Récupère un compte."""
    return os.environ[uid]


def main():
    # appel direct
    return fetch_account("x")
'''

CLASSES = """class Ledger:
    def fetch_account(self):
        return 1

    def total(self):
        return self.fetch_account()


class Other:
    def use(self, client):
        return client.fetch_account()
"""


def write(tmp_path: Path, files: object) -> None:
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


def read(tmp_path: Path, name: object) -> None:
    return (tmp_path / name).read_text(encoding="utf-8")


def test_renames_the_definition_the_calls_and_the_import(tmp_path: Path) -> None:
    root = write(tmp_path, {"app/mod.py": MODULE})
    rename(root, "fetch_account", "get_account")
    result = read(tmp_path, "app/mod.py")
    assert "def get_account(uid):" in result
    assert 'return get_account("x")' in result
    assert "from .helpers import get_account" in result
    assert "fetch_account" not in result


def test_leaves_the_rest_of_the_file_untouched(tmp_path: Path) -> None:
    root = write(tmp_path, {"app/mod.py": MODULE})
    rename(root, "fetch_account", "get_account")
    result = read(tmp_path, "app/mod.py")
    assert result == MODULE.replace("fetch_account", "get_account")


def test_renames_a_method_and_its_self_calls_in_the_owning_class(tmp_path: Path) -> None:
    root = write(tmp_path, {"app/mod.py": CLASSES})
    rename(root, "fetch_account", "get_account")
    result = read(tmp_path, "app/mod.py")
    assert "    def get_account(self):" in result
    assert "return self.get_account()" in result


def test_does_not_touch_an_attribute_on_an_unknown_object(tmp_path: Path) -> None:
    root = write(tmp_path, {"app/mod.py": CLASSES})
    report = rename(root, "fetch_account", "get_account")
    assert "client.fetch_account()" in read(tmp_path, "app/mod.py")
    assert any(w.kind == "attribute" for w in report.warnings)


def test_reports_the_name_inside_a_string(tmp_path: Path) -> None:
    root = write(tmp_path, {"app/mod.py": 'ROUTES = ["fetch_account"]\n'})
    report = rename(root, "fetch_account", "get_account")
    assert any(w.kind == "string" for w in report.warnings)
    assert '"fetch_account"' in read(tmp_path, "app/mod.py")


def test_reports_a_dynamic_access(tmp_path: Path) -> None:
    source = 'def go(s):\n    return getattr(s, "fetch_account")\n'
    root = write(tmp_path, {"app/mod.py": source})
    report = rename(root, "fetch_account", "get_account")
    assert any(w.kind == "dynamic access" for w in report.warnings)


def test_reports_occurrences_in_non_python_files(tmp_path: Path) -> None:
    root = write(
        tmp_path,
        {
            "app/mod.py": "def fetch_account():\n    pass\n",
            "templates/a.html": "{{ fetch_account }}\n",
        },
    )
    report = rename(root, "fetch_account", "get_account")
    assert any(w.kind == "non-Python" for w in report.warnings)


def test_refuses_when_the_new_name_already_exists(tmp_path: Path) -> None:
    source = "def fetch_account():\n    pass\n\ndef get_account():\n    pass\n"
    root = write(tmp_path, {"app/mod.py": source})
    report = rename(root, "fetch_account", "get_account")
    assert report.refusal is not None
    assert read(tmp_path, "app/mod.py") == source


def test_dry_run_writes_nothing_but_counts(tmp_path: Path) -> None:
    root = write(tmp_path, {"app/mod.py": MODULE})
    report = rename(root, "fetch_account", "get_account", dry_run=True)
    assert report.renamed == 3
    assert read(tmp_path, "app/mod.py") == MODULE


def test_warnings_use_paths_relative_to_the_root(tmp_path: Path) -> None:
    root = write(
        tmp_path,
        {
            "app/mod.py": "def fetch_account():\n    pass\n",
            "templates/a.html": "{{ fetch_account }}\n",
        },
    )
    report = rename(root, "fetch_account", "get_account", dry_run=True)
    assert any(w.path == "templates/a.html" for w in report.warnings)
