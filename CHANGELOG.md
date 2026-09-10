# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

First release.

### Added

- `check` — verdict on lexicon drift against a committed baseline, with rules
  D001 (a verb new to a family the repository already named), D002 (a known
  abbreviation whose full word is used elsewhere) and D003 (a name and a
  docstring describing different actions). Exit code 1 on findings.
- `dump` — the lexicon without judgement: verbs by family, most used nouns,
  and the vocabulary imposed by third-party libraries, broken down by reason.
  Text, JSON and TSV output. The JSON form doubles as the baseline.
- Test functions count as chosen vocabulary. Only the `test_` prefix is
  imposed by the tool; the rest is the author's, and often the clearest
  statement of intent in a repository.
- `rename` — renames occurrences whose target can be proven, and lists the
  ones it refuses to touch: attributes on an unknown receiver, string
  literals, dynamic access, and non-Python files.
- SARIF output, for GitHub's Security tab.
- Verb families and abbreviations in two editable JSON tables, covering
  English and French.

[Unreleased]: https://github.com/mathbeal/lexdrift/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mathbeal/lexdrift/releases/tag/v0.1.0
