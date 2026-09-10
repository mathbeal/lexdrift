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

CONFIG_NAME = "lexdrift.toml"


def load_config(root: str) -> dict[str, list[str]]:
    """Read the noun families a project declares for itself.

    Args:
        root: The directory to look in.

    Returns:
        Family name to the nouns that name it, empty when there is no file.

    Raises:
        ValueError: When a family is not written as a list of words.
    """
    path = os.path.join(root, CONFIG_NAME)
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as handle:
        document = tomllib.load(handle)

    families: dict[str, list[str]] = {}
    for family, members in document.get("nouns", {}).items():
        if not isinstance(members, list) or not all(
            isinstance(word, str) for word in members
        ):
            message = f'{CONFIG_NAME}: family "{family}" must be a list of words'
            raise ValueError(message)
        families[family] = list(members)
    return families
