"""Local preview: all built sites at once, each domain on its own port.

Every site runs from its own root (as on the server), so /assets/... paths work.
.htaccess rules (redirects, 404 page, caching) do not apply locally.

Usage: python scripts/serve.py [--port 8001]   (stop: Ctrl+C)
"""

import argparse
import functools
import http.server
import threading
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Local preview of the sites under dist/.")
    parser.add_argument("--port", type=int, default=8001, help="first port (default: 8001)")
    args = parser.parse_args()

    with open(ROOT / "src" / "sites.toml", "rb") as f:
        domains = list(tomllib.load(f)["sites"])
    for i, domain in enumerate(domains):
        root = DIST / domain
        if not root.is_dir():
            print(f"Missing: {root} (run python scripts/build.py first)")
            continue
        handler = functools.partial(QuietHandler, directory=str(root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port + i), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"{domain:24} http://localhost:{args.port + i}/   (live: https://{domain}/)")
    print("Stop: Ctrl+C")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
