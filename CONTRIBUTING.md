# Contributing

## Getting set up

```bash
git clone https://github.com/mathbeal/lexdrift
cd lexdrift
uv sync
just check          # or run the commands in AGENTS.md by hand
```

Without [uv](https://docs.astral.sh/uv/), `pip install -e ".[dev]"` works.

## What gets merged

Read [AGENTS.md](AGENTS.md) first — it states the rules the code holds to, and
they apply to humans as well.

Six gates must pass locally and in CI: `ruff check`, `ruff format --check`,
`mypy` in strict mode, the test suite at 100% branch coverage, `lexdrift check
lexdrift`, and `uv lock --check`.

Tests are written before the code. A pull request whose tests were written
afterwards is hard to distinguish from one whose tests were written to pass.

## Arguing with the tables

`lexdrift/synonyms.json` groups verbs into families; `lexdrift/abbreviations.json`
maps abbreviations to the words they stand for. Both are hand-written, and
disagreeing with a grouping is the intended use.

Open an issue saying which pairing is wrong and why. A verb belongs to exactly
one family — a test enforces it, so splitting a family means moving every verb
that belongs elsewhere.

## Reporting a false positive

Include the smallest source file that triggers it, the command you ran, and
what you expected instead. A false positive on a real repository is worth more
than a feature request.

## Commit messages

The changelog is generated from the history by `git-cliff`, so the first line of
a commit is what readers of the release will see. Prefix it with the kind of
change, then write the sentence as you would anyway:

```
feat: let a project declare its own noun families
fix: keep function words out of the glossary
docs: show what a good noun table looks like
refactor: move to pathlib and drop nine ruff exclusions
test: count a test function as chosen vocabulary
chore: refresh uv.lock after the version became dynamic
```

The prefix decides the section of the changelog; the sentence is the entry. A
commit without a prefix is still kept — it lands under *Changed*.

The body is not in the changelog. Use it, as before, to say why.

Regenerate with `just changelog`; `just changelog-check` fails if `CHANGELOG.md`
is not what the history produces.
