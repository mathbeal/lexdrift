# lexdrift

[![quality](https://github.com/mathbeal/lexdrift/actions/workflows/quality.yml/badge.svg)](https://github.com/mathbeal/lexdrift/actions/workflows/quality.yml)
[![python](https://img.shields.io/badge/python-3.9%20%E2%80%93%203.14-blue)](https://github.com/mathbeal/lexdrift)
[![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/mathbeal/lexdrift)
[![licence](https://img.shields.io/badge/licence-MIT-blue)](https://github.com/mathbeal/lexdrift/blob/main/LICENSE)

Read the lexicon of a Python repository — verbs, nouns, synonyms — setting aside the vocabulary imposed by third-party libraries.

Zero runtime dependencies. Python 3.9 to 3.14.

## What it does

lexdrift parses a repository with the standard library's `ast` module, extracts the identifiers of functions, methods and classes together with their docstrings, and builds a lexicon from them.

Before counting, it sets aside the names the author was not free to choose:

| Set aside | Reason |
|---|---|
| `__init__`, `__enter__` | language special method |
| Methods of a class deriving from a third-party base | third-party base class |
| Functions under a third-party decorator | third-party decorator |

A test function is *not* set aside. Only its `test_` prefix is imposed; `test_user_can_login` contributes `user`, `can` and `login` to the lexicon, and tests are often where a repository names its intentions most plainly.

`dump` reports the reasons separately, because a single share would conflate causes that have nothing to do with each other.

### What that measures

The share of imposed vocabulary separates applications from libraries.

| Repository | Names chosen | Imposed by a framework | Share |
|---|---:|---:|---:|
| [La Suite — Docs](https://github.com/suitenumerique/docs) (Django + DRF application) | 1,421 | 298 | **17%** |
| requests | 667 | 53 | 6.6% |
| pandas | 32,168 | 2,124 | 6.0% |
| rich | 1,658 | 137 | 6.5% |
| flask | 1,462 | 91 | 5.6% |
| pydantic | 12,566 | 409 | 2.9% |
| fastapi | 5,355 | 159 | 2.8% |
| django | 40,371 | 1,087 | 2.5% |
| scikit-learn | 11,531 | 309 | 2.4% |
| networkx | 7,906 | 63 | 0.8% |

A library defines its own vocabulary and inherits almost none. An application built on a framework inherits an order of magnitude more. Django itself sits at 2.5%; an application built on Django sits at 17%.

Every figure above is reproducible: clone the repository and run `lexdrift dump`.

### Why it matters more than it used to

Vocabulary drift used to be a matter of taste. It stopped being one when agents
started writing code.

An agent that meets `get_user` in one file and `fetch_user` in another has to
guess which one to use next, and it guesses badly — it has no memory of the
convention, only the evidence in front of it. Factory's agent-readiness rubric
scores *one term per concept* as the first of its seven dimensions, under
**Agent Contract**.

This repository holds itself to that rule: [AGENTS.md](AGENTS.md) states it,
and `lexdrift check lexdrift` enforces it in CI.

### Speed

Around 150,000 lines per second, linear, single pass, no dependencies. The whole of pandas — 710,000 lines across 1,524 files — takes under five seconds.

## Install

```bash
pip install lexdrift        # or: uv tool install lexdrift
```

From source:

```bash
git clone https://github.com/mathbeal/lexdrift
cd lexdrift
uv sync            # or: pip install -e .
```

The test suite, `mypy --strict` and `ruff` run on CPython 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14 in CI.

## Commands

```bash
lexdrift check .            # verdict: has the lexicon drifted? exit 0 or 1
lexdrift dump .             # the lexicon, no verdict, always exit 0
lexdrift rename OLD NEW .   # rename what can be proven, list the rest
```

`check` is the implicit command: `lexdrift .` behaves like `lexdrift check .`.

### `check`

Reports drift: a word introduced for an idea the repository already named.

| Rule | Reports |
|---|---|
| **D001** | A verb new to a family the repository already named — adding `fetch_*` where it said `get_*` |
| **D002** | A known abbreviation whose full word is used elsewhere — `usr` alongside `user` |
| **D003** | A name and a docstring describing different actions — `save_config()` documented as "Deletes…" |

D001 and D002 are measured against a baseline. D003 does not need one: it is a local inconsistency, not a property of the corpus.

```bash
lexdrift dump . --format json > lexdrift.lock   # commit this file
lexdrift check . --baseline lexdrift.lock
```

Without a baseline, every occurrence is reported and the run says so on stderr.

Exit code 1 when something is found, 0 otherwise. Output formats: `text`, `json`, `sarif`.

### `dump`

Prints the lexicon and never judges. Exit code is always 0.

```
$ lexdrift dump src/backend
351 names chosen, 1270 imposed

verbs, by family
  search     filter (4), search (3)  <- several
  convert    convert (4), serialize (2), parse (1), transform (1)  <- several
  create     create (7), build (5), generate (1)  <- several
  obtain     get (37)

most used nouns
  document (48), migration (32), serializer (25), user (16), access (15)

observations
  convert_markdown_to_html  family "convert": 4 verbs for one idea
  get_content               "get" spans two worlds: Response, api_view on one
                            side, BytesIO, pycrdt, requests on the other
```

Formats: `text`, `json`, `tsv`. The TSV form is one word per line, by decreasing frequency:

```
48	document	noun
37	get	verb	obtain
32	migration	noun
```

The JSON form doubles as the baseline consumed by `check --baseline`.

### `rename`

Renames the occurrences whose target can be proven, and lists the ones it refuses to touch.

| Case | Behaviour |
|---|---|
| Module function, its calls, its imports | renamed |
| Method, and `self.name` inside the class defining it | renamed |
| `object.name` elsewhere — receiver type unknown | listed, untouched |
| The name inside a string literal | listed, untouched |
| `getattr`, `setattr`, `hasattr` | listed, untouched |
| Templates, JSON, SQL, migrations | listed, untouched |

```
$ lexdrift rename get_abilities compute_abilities src/backend --dry-run
6 occurrences would be renamed across 1 files.

left untouched, to be checked:
  core/api/permissions.py:110   obj.get_abilities              (attribute)
  core/api/urls.py:31           'get_abilities'                (string)
  core/tasks.py:88              getattr(…, 'get_abilities')    (dynamic access)
  templates/document.html:12    get_abilities                  (non-Python)
```

Refuses on a modified git tree unless `--force`. Refuses when the new name already exists in the same scope. `--dry-run` writes nothing.

## Configuration

Two tables decide everything, and both ship with the package.

`lexdrift/synonyms.json` groups verbs into families. `lexdrift/abbreviations.json` maps abbreviations to the words they stand for. Both are hand-written, readable, and meant to be edited. Families cover English and French, conjugated and infinitive, so that a French codebase is not reported as verbless.

Rules are selected per run:

```bash
lexdrift check . --format sarif
lexdrift dump . --format tsv
```

## Design notes

**Two passes, not one.** A synonym cannot be decided at file scope: `get_user` in one file and `fetch_user` in another are only a problem together. Codexique reads the whole repository to build the lexicon, then judges each definition against it. As a consequence, a `pre-commit` hook restricted to changed files will not see drift — run it over the whole tree.

**Not a Ruff plugin.** Ruff has no plugin system, and its file-by-file single-pass architecture is incompatible with a corpus-wide rule.

**Drift, not state.** An imperfect lexicon is the normal state of any repository with history. `check` therefore compares against an accepted baseline rather than against perfection.

**No `--fix`.** Every correction lexdrift could make is a rename, and a rename is not a syntactic transformation: renaming a field in a Django model renames a database column, and Python does not allow the callers of a method to be enumerated. `rename` exists instead, and states what it could not resolve.

**Tables rather than a model.** No WordNet, no embeddings. A grouping you can open, read and contest is auditable; a similarity score is not.

**Locating with the AST, editing the text.** `rename` uses the AST only for positions, then edits the source right to left. Files stay byte-for-byte identical outside the positions that changed.

**Output versus diagnostics.** Findings, glossaries and reports go to stdout and are meant to be piped. Diagnostics about the run go through the `lexdrift` logger, on stderr.

## Limitations

- Python only. Multi-language support would require tree-sitter.
- The project/third-party boundary is resolved by path: anything under the analysed root is the project. This is wrong for unusual layouts.
- `dump` observations reason over the modules a body calls, not over semantics. They report heterogeneity; they do not prove a fault.
- A baseline is tied to the family keys of the shipped table. Editing `synonyms.json` invalidates it.

## Development

The project is managed with [uv](https://docs.astral.sh/uv/). `uv.lock` is committed, so every environment resolves identically.

```bash
uv sync
uv run ruff check lexdrift tests
uv run ruff format --check lexdrift tests
uv run mypy
uv run pytest --cov
```

Hooks run the same checks before each commit, plus `typos` and `zizmor`, which
audits the workflows:

```bash
uvx pre-commit install
```

To run the suite against another interpreter, uv fetches it if needed:

```bash
uv run --python 3.9 pytest
uv run --python 3.14 pytest
```

Without uv, `pip install -e ".[dev]"` works too.

`ruff` runs with every rule enabled; the exceptions are listed in `pyproject.toml` with their reason. `mypy` runs in strict mode. Coverage is enforced at 100%, branches included.

## Contributing

[AGENTS.md](AGENTS.md) is the contract — for agents and for people.
[CONTRIBUTING.md](CONTRIBUTING.md) covers the rest. `just check` runs every
gate CI runs.

## Licence

MIT.
