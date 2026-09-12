from __future__ import annotations

from lexdrift.attribution import classify
from lexdrift.collector import collect_source

SOURCE = """
from django.db import models
from .base import LocalMixin
import pytest


class Account(models.Model):
    def __init__(self):
        pass

    def save_account(self):
        pass


class Helper(LocalMixin):
    def build_report(self):
        pass


@pytest.fixture
def sample_payload():
    pass


def fetch_user():
    pass


def test_fetch_user():
    pass
"""


def classified() -> None:
    return classify([collect_source(SOURCE, module="app.models")], project_roots={"app"})


def names(definitions: object) -> None:
    return {d.name for d in definitions}


def test_dunder_methods_are_imposed() -> None:
    assert "__init__" in names(d for d, _ in classified().imposed)


def test_method_of_third_party_base_is_imposed() -> None:
    assert "save_account" in names(d for d, _ in classified().imposed)


def test_method_of_local_base_is_kept() -> None:
    assert "build_report" in names(classified().own)


def test_function_decorated_by_third_party_is_imposed() -> None:
    assert "sample_payload" in names(d for d, _ in classified().imposed)


def test_plain_module_function_is_kept() -> None:
    assert "fetch_user" in names(classified().own)


def test_a_test_function_is_chosen_vocabulary() -> None:
    """Only the ``test_`` prefix is imposed; the rest is the author's."""
    assert "test_fetch_user" in names(classified().own)


def test_imposed_definitions_carry_a_reason() -> None:
    reasons = {d.name: why for d, why in classified().imposed}
    assert reasons["save_account"] == "third-party base class"
