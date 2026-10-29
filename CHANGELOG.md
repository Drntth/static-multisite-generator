# Changelog

One entry per version. The version is kept in `pyproject.toml`.

## [Unreleased]

## [1.0.0] - 2026-10-29

- CI: tests, ruff and a build with internal link check on every push and pull request.
- `tools/check.sh` runs every check locally and in CI; `setup-hooks.sh` enables the pre-commit secret guard.
- Python 3.14+ required (`make venv` uses python3.14); pytest 9 and ruff 0.17 minimum.
- Baseline: earlier history in git log.
