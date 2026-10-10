"""Shared fixtures: a minimal source tree in a temporary folder.

The scripts read their folders from module-level paths (SRC, DIST, IMG_CACHE); the fixture points
them at tmp_path, so tests never touch the real src/ or dist/.
"""

from pathlib import Path

import pytest

import build
import check_links

SITES_TOML = """
[sites."a.example.com"]
name = "Site A"
short = "A"
schema_type = "Store"
accent = "#123456"
nav = [{ path = "/", label = "Home" }]

[sites."a.example.com".redirects]
"/old.html" = "/"

[sites."b.example.com"]
name = "Site B"
short = "B"
schema_type = "Store"
accent = "#654321"
nav = [{ path = "/", label = "Home" }]
"""

BASE = """<!doctype html>
<html>
  <head><title>{{ title }}</title>
  <meta name="description" content="{{ description }}" />
  {% if noindex | default(false) %}<meta name="robots" content="noindex" />{% endif %}
  </head>
  <body>
    <nav><a href="{{ link(domain, '/') }}">{{ site.name }}</a></nav>
{% block content %}{% endblock %}
  </body>
</html>
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def page(title: str, body: str, description: str = "Description.", noindex: bool = False) -> str:
    flags = "{% set noindex = true %}\n" if noindex else ""
    return (
        '{% extends "base.html" %}\n'
        f'{{% set title = "{title}" %}}\n{{% set description = "{description}" %}}\n{flags}'
        "{% block content %}\n" + body + "\n{% endblock %}\n"
    )


@pytest.fixture
def tree(tmp_path, monkeypatch) -> Path:
    src, dist = tmp_path / "src", tmp_path / "dist"
    write(src / "sites.toml", SITES_TOML)
    write(src / "shared" / "templates" / "base.html", BASE)
    write(
        src / "shared" / "templates" / "404.html",
        page("Not found", "<main>404</main>", noindex=True),
    )
    write(src / "shared" / "assets" / "css" / "main.css", "body { color: black; }\n")
    write(
        src / "sites" / "a.example.com" / "pages" / "index.html",
        page("Home A", "<main>A</main>"),
    )
    write(
        src / "sites" / "b.example.com" / "pages" / "index.html",
        page("Home B", "<main>B</main>"),
    )
    for module in (build, check_links):
        monkeypatch.setattr(module, "SRC", src)
        monkeypatch.setattr(module, "DIST", dist)
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "IMG_CACHE", tmp_path / ".cache" / "img")
    return tmp_path
