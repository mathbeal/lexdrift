from __future__ import annotations

from lexdrift.collector import collect_source

SOURCE = '''
import requests
from django.db import models
from .helpers import clean

CONSTANT = 1


def fetch_user(uid):
    """Retourne l'utilisateur."""
    return requests.get(uid)


class Account(models.Model):
    def __init__(self):
        pass

    @property
    def display_name(self):
        return clean(self.name)
'''


def parsed() -> None:
    return collect_source(SOURCE, module="app.models")


def test_collects_module_level_function() -> None:
    fetch = next(d for d in parsed().definitions if d.name == "fetch_user")
    assert fetch.kind == "function"
    assert fetch.qualname == "fetch_user"
    assert fetch.docstring == "Retourne l'utilisateur."


def test_collects_method_with_owning_class() -> None:
    method = next(d for d in parsed().definitions if d.name == "display_name")
    assert method.kind == "method"
    assert method.qualname == "Account.display_name"


def test_flags_dunder_methods() -> None:
    init = next(d for d in parsed().definitions if d.name == "__init__")
    assert init.is_dunder is True


def test_records_class_bases_as_written() -> None:
    account = next(d for d in parsed().definitions if d.name == "Account")
    assert account.kind == "class"
    assert account.bases == ["models.Model"]


def test_records_dotted_calls_made_in_a_body() -> None:
    fetch = next(d for d in parsed().definitions if d.name == "fetch_user")
    assert "requests.get" in fetch.calls


def test_records_decorators_as_written() -> None:
    method = next(d for d in parsed().definitions if d.name == "display_name")
    assert method.decorators == ["property"]


def test_maps_imported_names_to_their_root_module() -> None:
    imports = parsed().imports
    assert imports["requests"] == "requests"
    assert imports["models"] == "django.db"
    assert imports["clean"] == ".helpers"
