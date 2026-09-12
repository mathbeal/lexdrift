"""Split identifiers into the words they are made of."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

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


#: Words that glue a name together without naming anything: the ``as`` of
#: ``as_json``, the ``is`` of ``is_dirty``. A lexicon opening on them says
#: nothing about the repository.
FUNCTION_WORDS = frozenset({
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "not",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
})


def join_compounds(words: Sequence[str], compounds: Collection[str]) -> list[str]:
    """Join adjacent words that one declared term spells in several pieces.

    ``third`` and ``party`` are one concept. A lexicon that lists them
    apart invents two words the author never used.

    Args:
        words: The words of a name, in reading order.
        compounds: Declared terms, each written as a space-separated phrase.

    Returns:
        The same words, with every declared term joined into one entry.
    """
    sizes = sorted({len(t.split()) for t in compounds if " " in t}, reverse=True)
    joined: list[str] = []
    position = 0
    while position < len(words):
        for size in sizes:
            phrase = " ".join(words[position : position + size])
            if phrase in compounds:
                joined.append(phrase)
                position += size
                break
        else:
            joined.append(words[position])
            position += 1
    return joined


def chosen_nouns(words: Sequence[str], compounds: Collection[str] = ()) -> list[str]:
    """Keep the words of a name that name something.

    Declared terms are joined first, then function words are dropped. A name
    made of nothing else keeps them: it has nothing else to say.

    Args:
        words: The words of a name, in reading order.
        compounds: Declared multi-word terms.

    Returns:
        The nouns the name carries.
    """
    joined = join_compounds(words, compounds)
    kept = [word for word in joined if word not in FUNCTION_WORDS]
    return kept or joined
