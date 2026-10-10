"""Static build: src/ -> dist/<domain>/.

For every domain it:
- copies the shared (src/shared/assets) and the site-specific (src/sites/<domain>/assets) files;
  site-specific files override shared ones on the same path;
- renders the pages under src/sites/<domain>/pages with Jinja2 (shared templates: src/shared/templates),
  plus the shared 404 page;
- generates sitemap.xml, robots.txt, llms.txt and .htaccess;
- writes dist/CHANGED.txt: the files that changed since the previous build (these need uploading).

Usage: python scripts/build.py [domain ...]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
IMG_CACHE = ROOT / ".cache" / "img"

# Widths (px) of the responsive image variants; only those smaller than the source are made.
SRCSET_WIDTHS = (480, 800, 1200)
# srcset only for these classes (class -> sizes). Only images whose CSS gives them a definite width
# may get a srcset: with width: auto the browser takes the sizes value as the natural width and the
# image shrinks.
IMG_SIZES = {
    "hero-img": "100vw",
    "card-photo": "(min-width: 992px) 30vw, (min-width: 576px) 45vw, 90vw",
    "cover-img": "(min-width: 992px) 25vw, (min-width: 576px) 40vw, 80vw",
}

# HSTS: how long the browser opens the site over https only.
# Start with one day; raise it to 31536000 (one year) once https has been stable for a week or two.
HSTS_MAX_AGE = 86400


def load_sites() -> dict:
    with open(SRC / "sites.toml", "rb") as f:
        return tomllib.load(f)["sites"]


def page_url_path(rel: Path) -> str:
    """Path relative to pages/ -> URL path (index.html -> folder/)."""
    parts = rel.as_posix()
    if parts == "index.html":
        return "/"
    if parts.endswith("/index.html"):
        return "/" + parts[: -len("index.html")]
    return "/" + parts


def make_env(domain: str, site: dict) -> Environment:
    env = Environment(
        loader=FileSystemLoader([SRC / "sites" / domain / "pages", SRC / "shared" / "templates"]),
        undefined=StrictUndefined,
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )

    def link(target_domain: str, path: str) -> str:
        # Root-relative on the same domain, so the local preview works too.
        return path if target_domain == domain else f"https://{target_domain}{path}"

    def asset(rel: str) -> str:
        # CSS/JS: version parameter from the content hash, so browser caches never serve an old file.
        url = f"/assets/{rel}"
        if rel.endswith((".css", ".js")):
            for base in (SRC / "sites" / domain / "assets", SRC / "shared" / "assets"):
                if (base / rel).is_file():
                    return f"{url}?v={hashlib.sha256((base / rel).read_bytes()).hexdigest()[:8]}"
        return url

    # sites: every configured site, so shared templates can list them without hard-coded domains.
    env.globals.update(domain=domain, site=site, sites=load_sites(), link=link, asset=asset, body_class="")
    return env


def copy_assets(domain: str, out: Path) -> None:
    for base in (SRC / "shared" / "assets", SRC / "sites" / domain / "assets"):
        if base.is_dir():
            shutil.copytree(base, out / "assets", dirs_exist_ok=True)


def extract_meta(page: str) -> tuple[str, str, bool]:
    """Title, description and whether the page is noindex."""
    title = re.search(r"<title>(.*?)</title>", page, re.DOTALL)
    desc = re.search(r'<meta name="description" content="(.*?)"', page, re.DOTALL)
    return (
        html.unescape(title.group(1).strip()) if title else "",
        html.unescape(desc.group(1).strip()) if desc else "",
        '<meta name="robots" content="noindex"' in page,
    )


IMG_TAG = re.compile(r"<img\b[^>]*>", re.DOTALL)


def image_variant(file: Path, width: int) -> Path:
    """Smaller WebP variant next to file (named -<width>w.webp), from the cache if already made."""
    target = file.with_name(f"{file.stem}-{width}w.webp")
    if not target.is_file():
        key = hashlib.sha256(file.read_bytes()).hexdigest()[:16]
        cached = IMG_CACHE / f"{key}-{width}.webp"
        if not cached.is_file():
            IMG_CACHE.mkdir(parents=True, exist_ok=True)
            with Image.open(file) as im:
                im.thumbnail((width, width * 10), Image.Resampling.LANCZOS)
                im.save(cached, "WEBP", quality=82, method=6)
        shutil.copyfile(cached, target)
    return target


def add_srcset(tag: str, src: str, file: Path, natural_width: int) -> str:
    cls = re.search(r'class="([^"]*)"', tag)
    sizes = next((v for k, v in IMG_SIZES.items() if cls and k in cls.group(1).split()), None)
    widths = [w for w in SRCSET_WIDTHS if w < natural_width]
    if sizes is None or not widths or "srcset=" in tag:
        return tag
    base = src.rsplit("/", 1)[0] + "/" if "/" in src else ""
    entries = [f"{base}{image_variant(file, w).name} {w}w" for w in widths] + [f"{src} {natural_width}w"]
    return tag.replace("<img", f'<img srcset="{", ".join(entries)}" sizes="{sizes}"', 1)


def optimize_images(page: str, url_path: str, out: Path) -> str:
    """Improve image loading in the rendered HTML.

    - width/height from the real image size (the browser reserves the space: lower CLS); skipped when
      the tag already has a size. With img { width: auto; height: auto } in the CSS the attributes only
      set the aspect ratio, not the displayed size.
    - Images in <header> and the first image in <main> load immediately with high priority (LCP);
      the other images below the navigation load lazily.
    - Images below the navigation that are wider than 480 px also get smaller variants (srcset + sizes).
    """
    nav_end = page.find("</nav>")
    main_start = page.find("<main")
    first_main_img = IMG_TAG.search(page, main_start) if main_start >= 0 else None
    headers = [(m.start(), m.end()) for m in re.finditer(r"<header\b.*?</header>", page, re.DOTALL)]
    sizes: dict[Path, tuple[int, int]] = {}

    def fix(m: re.Match) -> str:
        tag = m.group(0)
        src = re.search(r'\ssrc="([^"]+)"', tag)
        if src:
            url = urlparse(urljoin(f"https://x{url_path}", src.group(1)))
            file = out / unquote(url.path).lstrip("/")
            if url.hostname == "x" and file.is_file():
                if file not in sizes:
                    with Image.open(file) as im:
                        sizes[file] = im.size
                w, h = sizes[file]
                if not re.search(r"\s(width|height)=", tag):
                    tag = tag.replace("<img", f'<img width="{w}" height="{h}"', 1)
                if m.start() > nav_end:
                    tag = add_srcset(tag, src.group(1), file, w)
        if m.start() < nav_end:
            return tag
        is_first_main = first_main_img is not None and m.start() == first_main_img.start()
        if is_first_main or any(a <= m.start() < b for a, b in headers):
            tag = re.sub(r'\sloading="lazy"', "", tag)
            if "fetchpriority=" not in tag:
                tag = tag.replace("<img", '<img fetchpriority="high"', 1)
        elif "loading=" not in tag:
            tag = tag.replace("<img", '<img loading="lazy"', 1)
        return tag

    return IMG_TAG.sub(fix, page)


def render(env: Environment, template: str, url_path: str, domain: str, out: Path, rel: str) -> str:
    def current(target_domain: str, path: str) -> bool:
        # True for the page being rendered (navigation highlight).
        return target_domain == domain and url_path == path

    page = env.get_template(template).render(current=current, page_path=url_path)
    page = optimize_images(page, url_path, out)
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(page, encoding="utf-8")
    return page


def render_pages(domain: str, site: dict, out: Path) -> list[dict]:
    """Indexable pages: URL path, title, description (the sitemap and llms.txt are built from these).
    noindex pages are rendered but not listed."""
    env = make_env(domain, site)
    pages_dir = SRC / "sites" / domain / "pages"
    pages = []
    for src in sorted(pages_dir.rglob("*.html")):
        rel = src.relative_to(pages_dir)
        if rel.name.startswith("_"):
            continue  # partial template, not a page
        url_path = page_url_path(rel)
        title, desc, noindex = extract_meta(render(env, rel.as_posix(), url_path, domain, out, rel.as_posix()))
        if noindex:
            continue
        pages.append({"path": url_path, "title": title, "description": desc})
    render(env, "404.html", "/404.html", domain, out, "404.html")
    return sorted(pages, key=lambda p: (p["path"] != "/", p["path"]))


def write_sitemap(domain: str, pages: list[dict], out: Path) -> None:
    urls = "".join(f"  <url><loc>https://{domain}{p['path']}</loc></url>\n" for p in pages)
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n",
        encoding="utf-8",
    )


def write_robots(domain: str, out: Path) -> None:
    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: https://{domain}/sitemap.xml\n", encoding="utf-8"
    )


def write_llms(domain: str, site: dict, pages: list[dict], out: Path) -> None:
    """llms.txt (llmstxt.org): a short Markdown overview for language models."""
    home = next((p for p in pages if p["path"] == "/"), pages[0] if pages else None)
    lines = [f"# {site['name']}", ""]
    if home:
        lines += [f"> {home['description']}", ""]
    lines += ["## Pages", ""]
    lines += [f"- [{p['title']}](https://{domain}{p['path']}): {p['description']}" for p in pages]
    # Downloadable files (e.g. PDF menus) of the site.
    docs = SRC / "sites" / domain / "assets" / "docs"
    files = sorted(f for f in docs.glob("*") if f.suffix in (".pdf", ".epub")) if docs.is_dir() else []
    if files:
        lines += ["", "## Downloads", ""]
        lines += [f"- [{f.name}](https://{domain}/assets/docs/{f.name})" for f in files]
    (out / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_htaccess(domain: str, site: dict, out: Path) -> None:
    lines = [
        "# Generated file (scripts/build.py), do not edit by hand.",
        "",
        "ErrorDocument 404 /404.html",
        "AddType font/woff2 .woff2",
        "AddType font/woff .woff",
        "",
        "# http -> https and www -> bare domain in a single 301 redirect",
        "RewriteEngine On",
        "RewriteCond %{HTTPS} off [OR]",
        "RewriteCond %{HTTP_HOST} ^www\\. [NC]",
        f"RewriteRule ^ https://{domain}%{{REQUEST_URI}} [L,R=301]",
        "",
        "<IfModule mod_headers.c>",
        f'  Header always set Strict-Transport-Security "max-age={HSTS_MAX_AGE}"',
        "</IfModule>",
    ]
    redirects = site.get("redirects", {})
    if redirects:
        lines += ["", "# Old URLs -> new pages"]
        lines += [f"Redirect 301 {old} {new}" for old, new in redirects.items()]
    lines += [
        "",
        "<IfModule mod_deflate.c>",
        "  AddOutputFilterByType DEFLATE text/html text/css text/plain application/javascript application/xml image/svg+xml",
        "</IfModule>",
        "",
        "# CSS/JS URLs carry a version parameter (?v=...), so they can be cached for long.",
        "<IfModule mod_expires.c>",
        "  ExpiresActive On",
        '  ExpiresByType text/css "access plus 1 year"',
        '  ExpiresByType application/javascript "access plus 1 year"',
        '  ExpiresByType image/webp "access plus 1 month"',
        '  ExpiresByType image/png "access plus 1 month"',
        '  ExpiresByType image/jpeg "access plus 1 month"',
        '  ExpiresByType application/pdf "access plus 1 week"',
        '  ExpiresByType font/woff2 "access plus 1 year"',
        '  ExpiresByType font/woff "access plus 1 year"',
        "</IfModule>",
    ]
    (out / ".htaccess").write_text("\n".join(lines) + "\n", encoding="utf-8")


def sync_dir(src: Path, dst: Path) -> None:
    """Copy src into dst without touching files whose content is unchanged.

    Unchanged files keep their modification time, so an FTP client's "overwrite if newer"
    comparison only picks the files that really changed.
    """
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        target = dst / f.relative_to(src)
        if target.is_file() and target.stat().st_size == f.stat().st_size and target.read_bytes() == f.read_bytes():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, target)
    for t in sorted(dst.rglob("*"), reverse=True):
        rel = t.relative_to(dst)
        if t.is_file() and not (src / rel).is_file():
            t.unlink()
        elif t.is_dir() and not (src / rel).is_dir():
            t.rmdir()


def file_hashes(base: Path) -> dict[str, str]:
    return {
        p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(base.rglob("*"))
        if p.is_file()
    }


def change_lines(old: dict, new: dict, domains: list[str]) -> list[str]:
    """Per-domain upload and delete list from two manifests ({"<domain>/<path>": sha256})."""
    lines = []
    for domain in domains:
        prefix = domain + "/"
        changed = [k[len(prefix) :] for k in new if k.startswith(prefix) and old.get(k) != new[k]]
        removed = [k[len(prefix) :] for k in old if k.startswith(prefix) and k not in new]
        if changed or removed:
            lines.append(f"== {domain}")
            lines += [f"  upload: {k}" for k in changed]
            lines += [f"  delete from server: {k}" for k in removed]
    return lines


def write_changes(old: dict, new: dict, domains: list[str], quiet: bool = False) -> None:
    lines = change_lines(old, new, domains)
    (DIST / "CHANGED.txt").write_text("\n".join(lines) + "\n" if lines else "No changes.\n", encoding="utf-8")
    if quiet:
        print(f"List of changed files: {(DIST / 'CHANGED.txt').relative_to(ROOT)}")
    else:
        print("\n".join(lines) if lines else "No changes since the previous build.")


def main(argv: list[str] | None = None) -> int:
    sites = load_sites()
    parser = argparse.ArgumentParser(description="Build the static sites into dist/.")
    parser.add_argument("domains", nargs="*", help="only these domains (default: all)")
    parser.add_argument("-q", "--quiet", action="store_true", help="do not list the changed files")
    args = parser.parse_args(argv)
    domains = args.domains or list(sites)
    unknown = [d for d in domains if d not in sites]
    if unknown:
        print(f"Unknown domain: {', '.join(unknown)}", file=sys.stderr)
        return 1

    DIST.mkdir(exist_ok=True)
    manifest = DIST / "manifest.json"
    old = json.loads(manifest.read_text()) if manifest.exists() else {}

    for domain in domains:
        site = sites[domain]
        tmp = DIST / f".build-{domain}"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        copy_assets(domain, tmp)
        pages = render_pages(domain, site, tmp)
        write_sitemap(domain, pages, tmp)
        write_robots(domain, tmp)
        write_llms(domain, site, pages, tmp)
        write_htaccess(domain, site, tmp)
        sync_dir(tmp, DIST / domain)
        shutil.rmtree(tmp)
        print(f"{domain}: {len(pages)} page(s)")

    new = {k: v for k, v in old.items() if k.split("/", 1)[0] not in domains}
    for domain in domains:
        new.update({f"{domain}/{k}": v for k, v in file_hashes(DIST / domain).items()})
    write_changes(old, new, domains, quiet=args.quiet)
    manifest.write_text(json.dumps(new, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
