#!/usr/bin/env bash
# Enables the pre-commit secret guard if it is not enabled yet (idempotent).
set -eu
cd "$(dirname "$0")"

current=$(git config --get core.hooksPath || true)
if [ "$current" = "tools/hooks" ]; then
  echo "Hook already enabled (core.hooksPath=tools/hooks)."
  exit 0
fi
if [ -n "$current" ]; then
  echo "Warning: core.hooksPath is '$current', overwriting it."
fi
git config core.hooksPath tools/hooks
echo "Hook enabled (core.hooksPath=tools/hooks)."
