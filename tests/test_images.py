"""Image loading attributes added to the rendered HTML."""

import re

from PIL import Image

import build

HTML = """<nav><img src="/assets/img/logo.png" alt="" /></nav>
<header><img src="/assets/img/hero.png" alt="Hero" /></header>
<main>
<img src="/assets/img/first.png" alt="First" />
<img class="card-photo" src="/assets/img/wide.png" alt="Wide" />
<img class="other" src="/assets/img/wide.png" alt="Unlisted" />
<img src="/assets/img/sized.png" alt="Sized" width="10" height="10" />
</main>"""


def make_images(out, tmp_path, monkeypatch):
    monkeypatch.setattr(build, "IMG_CACHE", tmp_path / "cache")
    img = out / "assets" / "img"
    img.mkdir(parents=True)
    for name, size in [
        ("logo", (32, 32)),
        ("hero", (300, 200)),
        ("first", (400, 300)),
        ("wide", (1000, 500)),
        ("sized", (50, 50)),
    ]:
        Image.new("RGB", size, "white").save(img / f"{name}.png")


def tags(html):
    return {re.search(r'alt="([^"]*)"', t).group(1): t for t in re.findall(r"<img\b[^>]*>", html)}


def test_images_get_their_real_size(tmp_path, monkeypatch):
    make_images(tmp_path, tmp_path, monkeypatch)
    out = tags(build.optimize_images(HTML, "/", tmp_path))
    assert 'width="1000" height="500"' in out["Wide"]
    assert 'width="10" height="10"' in out["Sized"] and 'width="50"' not in out["Sized"]


def test_header_and_first_main_image_load_with_high_priority(tmp_path, monkeypatch):
    make_images(tmp_path, tmp_path, monkeypatch)
    out = tags(build.optimize_images(HTML, "/", tmp_path))
    assert 'fetchpriority="high"' in out["Hero"] and "loading=" not in out["Hero"]
    assert 'fetchpriority="high"' in out["First"]
    assert 'loading="lazy"' in out["Wide"] and "fetchpriority" not in out["Wide"]


def test_navigation_images_get_no_loading_hints(tmp_path, monkeypatch):
    make_images(tmp_path, tmp_path, monkeypatch)
    out = tags(build.optimize_images(HTML, "/", tmp_path))
    assert "loading=" not in out[""] and "fetchpriority" not in out[""]


def test_srcset_only_for_listed_classes_and_smaller_widths(tmp_path, monkeypatch):
    make_images(tmp_path, tmp_path, monkeypatch)
    out = tags(build.optimize_images(HTML, "/", tmp_path))
    assert (
        'srcset="/assets/img/wide-480w.webp 480w, /assets/img/wide-800w.webp 800w, /assets/img/wide.png 1000w"'
        in out["Wide"]
    )
    assert 'sizes="' in out["Wide"]
    assert "srcset" not in out["Unlisted"]
    assert (tmp_path / "assets/img/wide-480w.webp").is_file()


def test_missing_image_files_are_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "IMG_CACHE", tmp_path / "cache")
    html = '<nav></nav><main><img src="/assets/img/none.png" alt="x" /></main>'
    assert build.optimize_images(html, "/", tmp_path) == html.replace("<img", '<img fetchpriority="high"')
