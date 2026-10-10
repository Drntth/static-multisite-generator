"""Rendering pages through the shared templates."""

from pathlib import Path

import pytest

import build
from conftest import page, write


def test_template_variables_are_html_escaped(tree):
    write(tree / "src/sites/a.example.com/pages/index.html", page("Fish & Chips <b>", "<main>A</main>"))
    build.main(["a.example.com", "-q"])
    html = (tree / "dist/a.example.com/index.html").read_text(encoding="utf-8")
    assert "<title>Fish &amp; Chips &lt;b&gt;</title>" in html


@pytest.mark.parametrize(
    ("rel", "url"),
    [("index.html", "/"), ("breads/index.html", "/breads/"), ("visit.html", "/visit.html")],
)
def test_page_file_maps_to_url_path(rel, url):
    assert build.page_url_path(Path(rel)) == url


def test_link_is_root_relative_on_the_same_domain_and_absolute_elsewhere(tree):
    env = build.make_env("a.example.com", build.load_sites()["a.example.com"])
    link = env.globals["link"]
    assert link("a.example.com", "/menu.html") == "/menu.html"
    assert link("b.example.com", "/menu.html") == "https://b.example.com/menu.html"


def test_css_asset_url_changes_with_its_content(tree):
    css = tree / "src/shared/assets/css/main.css"
    env = build.make_env("a.example.com", {})
    before = env.globals["asset"]("css/main.css")
    css.write_text("body { color: red; }\n", encoding="utf-8")
    after = env.globals["asset"]("css/main.css")
    assert before.startswith("/assets/css/main.css?v=") and len(before.split("=")[1]) == 8
    assert before != after


def test_site_css_overrides_the_shared_one_in_the_version_hash(tree):
    write(tree / "src/sites/a.example.com/assets/css/main.css", "body { color: green; }\n")
    a = build.make_env("a.example.com", {}).globals["asset"]("css/main.css")
    b = build.make_env("b.example.com", {}).globals["asset"]("css/main.css")
    assert a != b


def test_image_asset_url_has_no_version(tree):
    assert build.make_env("a.example.com", {}).globals["asset"]("img/logo.webp") == "/assets/img/logo.webp"


def test_site_asset_overrides_the_shared_file_on_the_same_path(tree):
    write(tree / "src/shared/assets/img/note.txt", "shared")
    write(tree / "src/sites/a.example.com/assets/img/note.txt", "site a")
    build.main(["-q"])
    assert (tree / "dist/a.example.com/assets/img/note.txt").read_text() == "site a"
    assert (tree / "dist/b.example.com/assets/img/note.txt").read_text() == "shared"


def test_partial_templates_are_not_rendered_as_pages(tree):
    write(tree / "src/sites/a.example.com/pages/_card.html", "<p>partial</p>")
    build.main(["a.example.com", "-q"])
    assert not (tree / "dist/a.example.com/_card.html").exists()


def test_unknown_domain_is_rejected(tree, capsys):
    assert build.main(["c.example.com"]) == 1
    assert "Unknown domain: c.example.com" in capsys.readouterr().err


def test_templates_see_every_configured_site(tree):
    env = build.make_env("a.example.com", build.load_sites()["a.example.com"])
    assert {d: s["name"] for d, s in env.globals["sites"].items()} == {
        "a.example.com": "Site A",
        "b.example.com": "Site B",
    }
