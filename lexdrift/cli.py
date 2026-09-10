"""Three commands, three contracts.

``check`` returns a verdict: 0 when the lexicon has not drifted, 1 otherwise.
``dump`` measures and never judges: it always returns 0.
``rename`` renames what it can prove and declares the rest.

Findings, glossaries and reports go to standard output: they are the product,
and they are meant to be piped. Diagnostics about the run itself go through
the logger, on standard error.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from typing import TYPE_CHECKING, Any

from . import __version__
from .drift import compare
from .project import findings, glossary, inspect
from .rename import rename
from .report import as_json, as_sarif, as_text
from .rules import load_families

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .project import Project

logger = logging.getLogger("lexdrift")

COMMANDS = ("check", "dump", "rename", "-h", "--help", "--version")


def build_parser() -> argparse.ArgumentParser:
    """Build the command line as it is documented.

    Returns:
        The parser, with its three subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="lexdrift",
        description=(
            "Read the lexicon of a Python repository. 'check' reports drift in "
            "the vocabulary, 'dump' measures it, 'rename' renames what can be "
            "proven. Vocabulary imposed by third-party libraries is set aside "
            "everywhere."
        ),
    )
    parser.add_argument("--version", action="version", version=f"lexdrift {__version__}")
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="verdict: has the lexicon drifted?")
    check.add_argument("path", nargs="?", default=".")
    check.add_argument(
        "--baseline",
        help="accepted state, produced by 'lexdrift dump --format json'",
    )
    check.add_argument("--format", choices=("text", "json", "sarif"), default="text")

    dump = sub.add_parser("dump", help="measure: the lexicon, without judgement")
    dump.add_argument("path", nargs="?", default=".")
    dump.add_argument(
        "--format",
        choices=("text", "json", "tsv"),
        default="text",
        help="tsv: one word per line, by decreasing frequency",
    )

    move = sub.add_parser("rename", help="rename what can be proven")
    move.add_argument("old")
    move.add_argument("new")
    move.add_argument("path", nargs="?", default=".")
    move.add_argument("--dry-run", action="store_true", help="write nothing")
    move.add_argument(
        "--force", action="store_true", help="proceed on a modified git tree"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line.

    Args:
        argv: Arguments to parse. Defaults to the process arguments.

    Returns:
        The exit code: 1 when 'check' found drift, 0 otherwise.
    """
    logging.basicConfig(format="lexdrift: %(message)s", level=logging.INFO)
    parser = build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in COMMANDS:
        arguments.insert(0, "check")
    options = parser.parse_args(arguments)

    if options.command == "rename":
        return _rename(options)

    project = inspect(options.path)
    if options.command == "dump":
        return _dump(project, options.format)
    return _check(project, options)


def tree_is_dirty(root: str) -> bool | None:
    """Ask git whether the working tree has changes.

    Args:
        root: The directory to ask about.

    Returns:
        True when git reports changes, False when it reports none, and None
        when the directory is not a git repository.
    """
    try:
        done = subprocess.run(  # noqa: S603 - fixed arguments, no user input
            ["git", "-C", str(root), "status", "--porcelain"],  # noqa: S607 - git is expected on PATH
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # pragma: no cover - git missing from the system
        return None
    if done.returncode != 0:
        return None
    return bool(done.stdout.strip())


def _rename(options: argparse.Namespace) -> int:
    """Rename, or refuse and say why.

    Args:
        options: The parsed command line.

    Returns:
        1 when the rename was refused, 0 otherwise.
    """
    dirty = tree_is_dirty(options.path)
    if dirty is None:
        logger.warning("not a git repository: this rename cannot be undone")
    elif dirty and not (options.force or options.dry_run):
        logger.error(
            "modified git tree: commit, or pass --force. You must be able to go back."
        )
        return 1

    report = rename(options.path, options.old, options.new, dry_run=options.dry_run)
    if report.refusal:
        logger.error(report.refusal)
        return 1

    verb = "would be renamed" if options.dry_run else "renamed"
    print(f"{report.renamed} occurrences {verb} across {len(report.files)} files.")
    if report.warnings:
        print("\nleft untouched, to be checked:")
        for warning in report.warnings:
            print(f"  {warning.path}:{warning.lineno}  {warning.text}  ({warning.kind})")
    return 0


def _check(project: Project, options: argparse.Namespace) -> int:
    """Return the verdict on lexicon drift.

    Args:
        project: The repository under scrutiny.
        options: The parsed command line.

    Returns:
        1 when something was found, 0 otherwise.
    """
    baseline = None
    if options.baseline:
        with open(options.baseline, encoding="utf-8") as handle:
            baseline = json.load(handle)

    found = compare(project, baseline)

    if options.format == "sarif":
        print(as_sarif(project, found))
    elif options.format == "json":
        print(as_json(project, found))
    else:
        if found:
            print(as_text(project, found))
        if found and not options.baseline:
            logger.info(
                "no baseline: everything is reported. "
                "Freeze the current state with 'lexdrift dump --format json'."
            )
    return 1 if found else 0


def _dump(project: Project, shape: str) -> int:
    """Dump the lexicon in the requested shape.

    Judges nothing, always returns 0.

    Args:
        project: The repository to measure.
        shape: One of ``text``, ``json`` or ``tsv``.

    Returns:
        Always 0.
    """
    lexicon = glossary(project)
    if shape == "json":
        print(json.dumps(lexicon, ensure_ascii=False, indent=2, sort_keys=True))
    elif shape == "tsv":
        print(as_tsv(lexicon))
    else:
        _print_report(lexicon)
        _print_observations(project)
    return 0


def as_tsv(lexicon: dict[str, Any]) -> str:
    """Render the lexicon as one tabulated word per line.

    Args:
        lexicon: The glossary to render.

    Returns:
        Count, word, kind and family, by decreasing frequency.
    """
    index = {v: f for f, group in load_families().items() for v in group}
    rows: list[tuple[int, str, str, str]] = [
        (n, w, "verb", index[w]) for w, n in lexicon["verbs"].items()
    ]
    rows += [(n, w, "noun", "") for w, n in lexicon["nouns"].items()]
    rows.sort(key=lambda row: (-row[0], row[1]))
    return "\n".join("\t".join(str(cell) for cell in row).rstrip("\t") for row in rows)


def _print_report(lexicon: dict[str, Any]) -> None:
    """Print the lexicon in plain words.

    Args:
        lexicon: The glossary to print.
    """
    print(f"{lexicon['own']} names chosen, {lexicon['imposed']} imposed")
    print("\nverbs, by family")
    for family, verbs in sorted(lexicon["families"].items()):
        ordered = sorted(verbs.items(), key=lambda kv: (-kv[1], kv[0]))
        rendered = ", ".join(f"{v} ({n})" for v, n in ordered)
        marker = "  <- several" if len(verbs) > 1 else ""
        print(f"  {family:<10} {rendered}{marker}")
    print("\nmost used nouns")
    top = sorted(lexicon["nouns"].items(), key=lambda kv: (-kv[1], kv[0]))[:20]
    print("  " + ", ".join(f"{w} ({n})" for w, n in top))


def _print_observations(project: Project) -> None:
    """Print what the lexicon says about the corpus.

    These are measurements, never faults.

    Args:
        project: The repository to observe.
    """
    watched = [f for f in findings(project) if f.rule in ("L001", "L005")]
    if not watched:
        return
    print("\nobservations")
    for finding in watched:
        print(f"  {finding.qualname} {finding.message}")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
