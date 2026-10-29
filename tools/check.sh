#!/usr/bin/env bash
# Checks: pytest, ruff, build, internal link check (offline, no external links). The same script runs locally and in CI.
set -u
cd "$(dirname "$0")/.."

failed=()

# Python: the project .venv if present, else python3 from PATH (CI)
PY=$([ -x .venv/bin/python ] && echo .venv/bin/python || command -v python3)

step() {
  local name=$1
  shift
  echo "== $name"
  if ! "$@"; then failed+=("$name"); fi
}

step "pytest" "$PY" -m pytest -q
step "ruff check" "$PY" -m ruff check scripts tests
step "ruff format" "$PY" -m ruff format --check scripts tests
step "build" "$PY" scripts/build.py
step "link check" "$PY" scripts/check_links.py

if [ "${#failed[@]}" -gt 0 ]; then
  echo "FAILED: ${failed[*]}"
  exit 1
fi
echo "All checks passed."
