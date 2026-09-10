"""What a project declares about its own vocabulary.

Verbs form a closed universal set: ``get``, ``fetch`` and ``retrieve`` mean
the same thing in every repository, so the table ships with the tool. Nouns
do not. ``user``, ``account`` and ``customer`` are the same person in one
domain and three different things in another, and no shipped table can know
which. A project declares its own, or declares nothing.
"""

from __future__ import annotations

import os
import tomllib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

CONFIG_NAME = "lexdrift.toml"
SHARED_NAME = "pyproject.toml"


def _load_section(directory: str) -> Mapping[str, Any] | None:
    """Read the lexdrift settings held in one directory.

    A dedicated file wins over the shared one, so that a project can
    override what its ``pyproject.toml`` says.

    Args:
        directory: The directory to look in.

    Returns:
        The settings found, or None when this directory holds none.
    """
    own = os.path.join(directory, CONFIG_NAME)
    if os.path.exists(own):
        with open(own, "rb") as handle:
            settings: Mapping[str, Any] = tomllib.load(handle)
        return settings
    shared = os.path.join(directory, SHARED_NAME)
    if os.path.exists(shared):
        with open(shared, "rb") as handle:
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
    current = os.path.abspath(root)
    while True:
        settings = _load_section(current)
        if settings is not None:
            return settings
        if os.path.isdir(os.path.join(current, ".git")):
            return {}
        parent = os.path.dirname(current)
        if parent == current:
            return {}
        current = parent


def load_config(root: str) -> dict[str, list[str]]:
    """Read the noun families a project declares for itself.

    Args:
        root: The directory the analysis started from.

    Returns:
        Family name to the nouns that name it, empty when nothing is
        declared.

    Raises:
        ValueError: When a family is not written as a list of words.
    """
    families: dict[str, list[str]] = {}
    for family, members in _load_settings(root).get("nouns", {}).items():
        if not isinstance(members, list) or not all(
            isinstance(word, str) for word in members
        ):
            message = f'"{family}" must be declared as a list of words'
            raise ValueError(message)
        families[family] = list(members)
    return families
