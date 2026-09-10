# Agent contract

This file tells an automated agent how to work in this repository. It is the
contract; `CLAUDE.md` points here.

## One term per concept

The repository names one idea one way. `get` or `fetch`, never both. `path` or
`filepath`, never both.

This is not a style preference. An agent that meets `get_user` in one file and
`fetch_user` in another has to guess which one to use next, and it guesses
badly. The rule is enforced, not suggested: `lexdrift check lexdrift` runs in
CI and fails on a verb introduced for an idea already named.

Before adding a name, run `lexdrift dump lexdrift` and reuse a word already in
the lexicon.

## What the code is

A linter that reads the lexicon of a Python repository. Three commands, three
contracts:

- `check` returns a verdict on drift — exit 0 or 1
- `dump` measures and never judges — always exit 0
- `rename` renames what it can prove and lists what it cannot

Keep these contracts separate. Findings, glossaries and reports go to stdout,
because they are the product and they get piped. Diagnostics about the run go
through the `lexdrift` logger, on stderr.

## Rules that hold everywhere

**Zero runtime dependencies.** Only the standard library. Adding one needs a
reason written in the pull request, not a convenience.

**Python 3.9 is the floor.** `ruff` targets `py39` and CI runs the suite on a
real 3.9. Anything unavailable there is a bug.

**Tests come first.** Write the failing test, watch it fail, then write the
code. Coverage is enforced at 100%, branches included.

**The tables are data, not code.** `synonyms.json` and `abbreviations.json` are
hand-written and meant to be argued with. A verb belongs to exactly one family;
a test enforces it.

**Never reformat what you did not change.** `rename` locates with the AST and
edits the text, so files stay byte-for-byte identical outside the positions
that changed. Hold the same standard by hand.

## Before opening a pull request

```bash
uv sync --all-extras
uv run ruff check lexdrift tests
uv run ruff format --check lexdrift tests
uv run mypy
uv run pytest --cov
uv run lexdrift check lexdrift
```

All six must pass. CI runs the same, plus `typos`, `zizmor`, and the suite on
Python 3.9 through 3.14.
