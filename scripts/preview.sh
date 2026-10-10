#!/usr/bin/env bash
# README image: screenshots of every site's home page (1280x900), side by side in docs/preview.png.
# Needs a finished build (dist/), Google Chrome (headless) and ImageMagick.
# Usage: scripts/preview.sh [first port, default 8101]
set -euo pipefail

cd "$(dirname "$0")/.."
port="${1:-8101}"
py=.venv/bin/python
tmp="$(mktemp -d)"

for tool in google-chrome convert; do
    command -v "$tool" >/dev/null || { echo "Missing: $tool" >&2; exit 1; }
done
[[ -d dist ]] || { echo "No dist/ folder; run make build first." >&2; exit 1; }

"$py" scripts/serve.py --port "$port" >/dev/null &
server=$!
trap 'kill "$server" 2>/dev/null; rm -rf "$tmp"' EXIT

count="$("$py" -c 'import tomllib; print(len(tomllib.load(open("src/sites.toml", "rb"))["sites"]))')"
last=$((port + count - 1))
for _ in $(seq 50); do
    curl -s -o /dev/null "http://127.0.0.1:$last/" && break
    sleep 0.1
done

shots=()
for i in $(seq 0 $((count - 1))); do
    shot="$tmp/$i.png"
    google-chrome --headless=new --disable-gpu --hide-scrollbars --window-size=1280,900 \
        --virtual-time-budget=3000 --screenshot="$shot" "http://127.0.0.1:$((port + i))/" >/dev/null 2>&1
    shots+=("$shot")
done

mkdir -p docs
convert "${shots[@]}" -resize 600x -bordercolor "#dddddd" -border 1 +append -strip docs/preview.png
echo "docs/preview.png: $count site(s)"
