"""Find broken links in the built pages under dist/.

- Internal links (relative, root-relative) and links between the configured domains: checked
  against the files in dist/.
- External links (--external): checked with HTTP requests.

Usage: python scripts/check_links.py [--external]
Exit code: 0 if there are no errors, 1 if a link is broken.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DIST = ROOT / "dist"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        for name, value in attrs:
            if not value:
                continue
            if name == "srcset":
                # "a-480w.webp 480w, a.webp 1200w": the first part of every comma-separated candidate is a URL.
                self.links += [c.split()[0] for c in value.split(",") if c.strip()]
            elif name in ("href", "src") and not (
                tag == "link" and name == "href" and "preconnect" in dict(attrs).get("rel", "")
            ):
                self.links.append(value)


def resolve_local(domain: str, path: str) -> bool:
    target = DIST / domain / unquote(path).lstrip("/")
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target.is_file()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find broken links under dist/.")
    parser.add_argument("--external", action="store_true", help="check external links with HTTP requests")
    args = parser.parse_args(argv)

    with open(SRC / "sites.toml", "rb") as f:
        domains = set(tomllib.load(f)["sites"])
    if not DIST.is_dir():
        print("No dist/ folder; run python scripts/build.py first.", file=sys.stderr)
        return 1

    errors: list[str] = []
    external: dict[str, list[str]] = {}
    for domain in sorted(domains):
        for page in sorted((DIST / domain).rglob("*.html")):
            rel = page.relative_to(DIST / domain).as_posix()
            base = f"https://{domain}/{rel}"
            p = LinkParser()
            p.feed(page.read_text(encoding="utf-8"))
            for link in p.links:
                if link.startswith(("mailto:", "tel:", "#", "data:", "javascript:")) or link == "":
                    continue
                url = urlparse(urljoin(base, link))
                where = f"{domain}/{rel}: {link}"
                if url.scheme == "http" and url.hostname in domains:
                    errors.append(f"{where} (needs https instead of http)")
                if url.hostname in domains:
                    if not resolve_local(url.hostname, url.path or "/"):
                        errors.append(f"{where} (no such file)")
                else:
                    external.setdefault(url._replace(fragment="").geturl(), []).append(where)

    if args.external:
        import requests

        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) check_links"}

        for url, wheres in sorted(external.items()):
            try:
                r = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
                if r.status_code >= 400:
                    r = requests.get(url, allow_redirects=True, timeout=10, headers=headers)
                if r.status_code >= 400:
                    errors += [f"{w} (HTTP {r.status_code})" for w in wheres]
            except requests.RequestException as e:
                errors += [f"{w} ({type(e).__name__})" for w in wheres]
    else:
        print(f"{len(external)} external link(s) not checked (--external).")

    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
