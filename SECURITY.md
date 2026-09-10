# Security

## Scope

lexdrift reads source files and, with `rename`, writes them back. It has no
runtime dependencies, makes no network calls, and executes nothing it reads —
files are parsed with the standard library's `ast` module, never imported.

`rename` is the only command that writes. It refuses to run on a modified git
tree unless forced, so that any change can be undone with `git checkout`.

## Reporting a vulnerability

Open a [security advisory](https://github.com/mathbeal/lexdrift/security/advisories/new).
Please do not open a public issue for a vulnerability.

Expect a first answer within a week.

## Supported versions

The latest release only.
