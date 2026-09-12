# Run `just` to see the recipes.
default:
    @just --list

# Install the project and its development tools.
setup:
    uv sync

# Every gate CI runs, in the same order.
check: lint types test self lock

lint:
    uv run ruff check lexdrift tests
    uv run ruff format --check lexdrift tests

types:
    uv run mypy

test:
    uv run pytest --cov

# The tool must pass on its own code.
self:
    uv run lexdrift check lexdrift

lock:
    uv lock --check

# Reformat and apply the safe fixes.
fix:
    uv run ruff check lexdrift tests --fix
    uv run ruff format lexdrift tests

# Audit the workflows and hunt typos, as CI does.
hygiene:
    uvx typos .
    uvx zizmor --persona=regular .github/workflows/

# Build the wheel and the sdist, and check them.
build:
    rm -rf dist
    uv build
    uv run --no-project --with twine twine check --strict dist/*

# Regenerate CHANGELOG.md from the commit history.
changelog:
    git-cliff -o CHANGELOG.md

# Fail if CHANGELOG.md is not what the history produces.
changelog-check:
    git-cliff -o /tmp/cliff-expected.md
    diff -u CHANGELOG.md /tmp/cliff-expected.md

# Known vulnerabilities in the locked dependencies (PyPA advisory database).
audit:
    uv export --frozen --no-emit-project --all-groups -o /tmp/lexdrift-req.txt
    uvx pip-audit --strict --disable-pip -r /tmp/lexdrift-req.txt
