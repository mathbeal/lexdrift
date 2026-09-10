"""Reports: for a human, for a machine, for GitHub."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .project import Project, paths

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .rules import Finding

RULES = {
    "D001": "A new verb for an idea already named",
    "D002": "A new abbreviation of a word spelled out elsewhere",
    "D003": "The name and the docstring do not say the same thing",
    "D004": "A new noun for an idea the project already named",
}


def as_text(project: Project, findings: Iterable[Finding]) -> str:
    """Render findings one per line, in the format editors can open.

    Args:
        project: The repository the findings came from.
        findings: What to render.

    Returns:
        ``path:line: RULE message`` for each finding.
    """
    where = paths(project)
    return "\n".join(
        f"{where.get(f.module, f.module)}:{f.lineno}: {f.rule} {f.message}"
        for f in findings
    )


def as_json(project: Project, findings: Iterable[Finding]) -> str:
    """Render findings as JSON, to be consumed by another tool.

    Args:
        project: The repository the findings came from.
        findings: What to render.

    Returns:
        A JSON array, one object per finding.
    """
    where = paths(project)
    payload = [
        {
            "rule": f.rule,
            "path": where.get(f.module, f.module),
            "line": f.lineno,
            "qualname": f.qualname,
            "message": f.message,
        }
        for f in findings
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def as_sarif(project: Project, findings: Iterable[Finding]) -> str:
    """Render findings as SARIF, which GitHub displays natively.

    Args:
        project: The repository the findings came from.
        findings: What to render.

    Returns:
        A SARIF 2.1.0 document.
    """
    where = paths(project)
    document: dict[str, Any] = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "lexdrift",
                        "informationUri": "https://github.com/mathbeal/lexdrift",
                        "rules": [
                            {
                                "id": rule,
                                "name": rule,
                                "shortDescription": {"text": text},
                            }
                            for rule, text in sorted(RULES.items())
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": f.rule,
                        "level": "note",
                        "message": {"text": f.message},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": where.get(f.module, f.module)
                                    },
                                    "region": {"startLine": f.lineno},
                                }
                            }
                        ],
                    }
                    for f in findings
                ],
            }
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2)
