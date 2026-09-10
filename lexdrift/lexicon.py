"""Split identifiers into the words they are made of."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|[0-9]+")

#: Words a tool puts at the head of a name. Only the prefix is imposed; what
#: follows it is the author's vocabulary, and often the most telling of the
#: repository — a test names an intention.
CONVENTION_WORDS = ("test",)


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


def split_chosen_words(name: str) -> list[str]:
    """Split an identifier, dropping a leading word imposed by a tool.

    ``test_fetch_account`` yields the vocabulary of ``fetch_account``: pytest
    dictates the prefix, not the rest. A name that merely starts with the
    same letters, such as ``testament_parser``, is left alone.

    Args:
        name: The identifier to split.

    Returns:
        The words the author chose, lowercased.
    """
    words = split_identifier(name)
    if len(words) > 1 and words[0] in CONVENTION_WORDS:
        return words[1:]
    return words
