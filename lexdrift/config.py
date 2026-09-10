"""What a project declares about its own vocabulary.

Verbs form a closed universal set: ``get``, ``fetch`` and ``retrieve`` mean
the same thing in every repository, so the table ships with the tool. Nouns
do not. ``user``, ``account`` and ``customer`` are the same person in one
domain and three different things in another, and no shipped table can know
which. A project declares its own, or declares nothing.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class ConfigError(ValueError):
    """What a project declared cannot be used, and here is why."""


CONFIG_NAME = "lexdrift.toml"
SHARED_NAME = "pyproject.toml"


def _load_section(directory: Path) -> Mapping[str, Any] | None:
    """Read the lexdrift settings held in one directory.

    A dedicated file wins over the shared one, so that a project can
    override what its ``pyproject.toml`` says.

    Args:
        directory: The directory to look in.

    Returns:
        The settings found, or None when this directory holds none.
    """
    own = directory / CONFIG_NAME
    if own.exists():
        with own.open("rb") as handle:
            settings: Mapping[str, Any] = tomllib.load(handle)
        return settings
    shared = directory / SHARED_NAME
    if shared.exists():
        with shared.open("rb") as handle:
            document = tomllib.load(handle)
        section: Mapping[str, Any] = document.get("tool", {}).get("lexdrift", {})
        return section
    return None


def _load_settings(root: str) -> Mapping[str, Any]:
    """Walk up from a directory until the settings are found.

    A repository is configured at its root and analysed by the
    subdirectory, so the search climbs. It stops at the repository
    boundary: what lies above belongs to somebody else.

    Args:
        root: The directory the analysis started from.

    Returns:
        The settings found, empty when there are none.
    """
    current = Path(root).resolve()
    while True:
        settings = _load_section(current)
        if settings is not None:
            return settings
        if (current / ".git").is_dir():
            return {}
        if current.parent == current:
            return {}
        current = current.parent


def load_config(root: str) -> dict[str, list[str]]:
    """Read the noun families a project declares for itself.

    Args:
        root: The directory the analysis started from.

    The family name is itself a member: writing ``user = ["customer"]``
    declares both, because the key is the obvious canonical word and
    forgetting to repeat it would silently declare a family of one, which
    no rule can ever report. Everything is lowercased, since identifiers
    are read lowercased.

    Returns:
        Family name to the nouns that name it, empty when nothing is
        declared.

    Raises:
        ConfigError: When a family is not written as a list of words, or
            when one noun is claimed by two families.
    """
    families: dict[str, list[str]] = {}
    claimed: dict[str, str] = {}
    for name, members in _load_settings(root).get("nouns", {}).items():
        if not isinstance(members, list) or not all(
            isinstance(word, str) for word in members
        ):
            message = f'"{name}" must be declared as a list of words'
            raise ConfigError(message)
        family = name.lower()
        words: list[str] = []
        for word in [family, *(m.lower() for m in members)]:
            if word in words:
                continue
            if word in claimed and claimed[word] != family:
                message = (
                    f'"{word}" is declared in two families, '
                    f'"{claimed[word]}" and "{family}": it can only mean one'
                )
                raise ConfigError(message)
            claimed[word] = family
            words.append(word)
        families[family] = words
    return families
