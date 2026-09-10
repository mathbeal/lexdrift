from __future__ import annotations

from lexdrift.lexicon import split_identifier


def test_splits_snake_case() -> None:
    assert split_identifier("get_user_name") == ["get", "user", "name"]


def test_splits_camel_case() -> None:
    assert split_identifier("getUserName") == ["get", "user", "name"]


def test_splits_pascal_case() -> None:
    assert split_identifier("UserAccount") == ["user", "account"]


def test_keeps_acronym_together() -> None:
    assert split_identifier("HTTPServer") == ["http", "server"]


def test_separates_digits() -> None:
    assert split_identifier("parse_utf8_header") == ["parse", "utf", "8", "header"]


def test_ignores_leading_and_trailing_underscores() -> None:
    assert split_identifier("__private_helper__") == ["private", "helper"]


def test_single_word() -> None:
    assert split_identifier("save") == ["save"]
