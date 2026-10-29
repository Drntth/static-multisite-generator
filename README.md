# static-multisite-generator

English | [Magyar](README.hu.md)

A small Python and Jinja2 generator for several static websites from one source. Built for shared Apache hosting with FTP upload: no server-side runtime, no Node toolchain, and a build that does the performance and SEO work for you. The repository ships with three fictional sample sites (a bakery, a café and a bookshop of the same family business).

![Home pages of the three sample sites](docs/preview.png)

## Features

- **Several domains, one source:** shared templates and assets with per-site overrides; a fix in the shared layer reaches every site.
- **Links between sites:** `link(domain, path)` gives a root-relative link on the same domain and an absolute `https://` link to another one, so the local preview works too.
- **Image work in the build:** every `<img>` gets its real `width`/`height`; header images and the first image of `<main>` get `fetchpriority="high"`, the rest `loading="lazy"`; listed classes get `srcset` variants in WebP.
- **Generated meta files per domain:** `sitemap.xml`, `robots.txt`, `llms.txt` and `.htaccess` (https and bare-domain 301, old-URL redirects, HSTS, compression, cache headers).
- **Upload-friendly output:** unchanged files keep their modification time, and `dist/CHANGED.txt` lists what to upload and what to delete since the previous build (from a SHA-256 manifest).
- **Cache busting:** CSS and JS URLs carry a content-hash version (`main.css?v=1a2b3c4d`), so they can be cached for a year.
- **No third-party requests:** Bootstrap, Bootstrap Icons and the fonts are served from the site itself, with a license register.
- **Checks:** strict template variables, HTML autoescaping, and a link checker for internal links, links between the sites and (optionally) external links.

## Requirements

- Python 3.14+
- For the README preview only: Google Chrome (headless) and ImageMagick

## Quick start

```bash
make venv        # .venv with Jinja2, Pillow, requests, pytest, ruff (python3.14 by default, PYTHON=... to override)
make build       # dist/<domain>/ for every site + dist/CHANGED.txt
make check       # link check on dist/
make serve       # local preview: one port per site, from 8001
```

## Commands

```bash
.venv/bin/python scripts/build.py [domain ...] [-q]           # build all or some sites
.venv/bin/python scripts/check_links.py [--external]          # 0 = no broken links
.venv/bin/python scripts/convert_images.py <path> [--max-size 1920] [--keep] [--dry-run]
.venv/bin/python scripts/serve.py [--port 8001]
make test                                                       # pytest
make lint                                                       # ruff
make preview                                                    # docs/preview.png from the built sites
```

## How it works

```text
src/sites.toml                  domains, names, accent colours, menus, old-URL redirects
src/shared/templates/           base.html, 404.html, partials/ (head, nav, footer)
src/shared/assets/              css/, js/, img/, fonts/, vendor/ (shared by every site)
src/sites/<domain>/pages/       page templates; each extends base.html
src/sites/<domain>/assets/      site-specific assets; override shared files on the same path
scripts/build.py                build into dist/<domain>/, manifest and change list
dist/                           output (gitignored), uploaded as is
```

For every domain the build copies the shared and then the site assets, renders each page, post-processes the images in the HTML, writes the meta files into a temporary folder and syncs it into `dist/<domain>/`, touching only files whose content changed.

### Pages

A page is a template under `src/sites/<domain>/pages/`:

```jinja
{% extends "base.html" %}
{% set title = "Breads | Example Bakery" %}
{% set description = "Our daily breads." %}
{% block content %}
    <main class="container py-5">...</main>
{% endblock %}
```

- `index.html` becomes `/`, `breads/index.html` becomes `/breads/`, `visit.html` stays `/visit.html`.
- Set `noindex = true` to keep a page out of the sitemap and `llms.txt`.
- Files starting with `_` are partials, not pages.
- Write exactly one `<h1>` per page and a meaningful `alt` for every image.

### Images

- Convert images with `scripts/convert_images.py` (WebP, rotated by EXIF, max. 1920 px).
- Add a class to `IMG_SIZES` in `scripts/build.py` only if its CSS gives the image a definite width; with `width: auto` the browser treats the `sizes` value as the natural width and the image shrinks.

### Deploying

Upload `dist/<domain>/` to the web root of each domain. The upload list for the last build is in `dist/CHANGED.txt`; with an FTP client's "overwrite if newer" mode the unchanged files are skipped, because their modification time is kept. Show hidden files to upload `.htaccess`.

## Project structure

```text
scripts/    build.py, check_links.py, convert_images.py, serve.py
src/        sites.toml, shared/, sites/<domain>/
tests/      pytest suite (runs against a temporary source tree)
docs/       README preview image
```

## Known limitations

- `.htaccess` targets Apache; other servers need their own redirect and cache rules.
- There is no upload script: the change list is meant for a manual or `lftp`-based upload.
- The sample images are generated placeholders.

## License

MIT, see [LICENSE](LICENSE). Bootstrap and Bootstrap Icons (MIT) and the Inter and Playfair Display fonts (SIL OFL 1.1) keep their own licenses; see `LICENSES.md` in `src/shared/assets/vendor/` and `src/shared/assets/fonts/`.
