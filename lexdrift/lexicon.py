"""Split identifiers into the words they are made of."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|[0-9]+")


def split_identifier(name: str) -> list[str]:
    """Split an identifier into lowercase words.

    Handles ``snake_case``, ``camelCase``, ``PascalCase``, glued acronyms
    such as ``HTTPServer``, and digits such as ``utf8``. Leading and
    trailing underscores are ignored.

    Args:
        name: The identifier to split.

    Returns:
        The words it is made of, lowercased, in reading order.
    """
    words: list[str] = []
    for chunk in name.strip("_").split("_"):
        words.extend(match.group(0).lower() for match in _TOKEN.finditer(chunk))
    return words
