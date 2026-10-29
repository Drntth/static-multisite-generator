# static-multisite-generator

Commit prefix: [STATIC-MULTISITE]

## Purpose

Python + Jinja2 generator for several static websites from one source, for shared Apache hosting with FTP upload. Ships with three fictional sample sites (`bakery`, `cafe`, `books` on `example.com`). Domain terms: `CONTEXT.md`.

## Stack

Python 3.14+, Jinja2, Pillow, requests (external link check only); pytest, ruff. Front end: Bootstrap 5.3.8 and Bootstrap Icons 1.11.3, Inter and Playfair Display, all self-hosted.

## Commands

```bash
make venv                     # .venv with python3.14 (PYTHON=... to override, 3.14+ checked)
make build                    # dist/<domain>/ + dist/CHANGED.txt
make check                    # link check, must report 0 errors
make test                     # pytest
make lint                     # ruff check + format --check
make serve                    # preview, one port per site from 8001
make preview                  # docs/preview.png (Chrome + ImageMagick)
```

Done when: `make build`, `make check`, `make test` and `make lint` pass, and a second `make build` reports "No changes".

## Structure

- `src/sites.toml`: sites, menus, accent colours, `redirects`.
- `src/shared/templates/`, `src/shared/assets/`: shared layer. `src/sites/<domain>/`: pages and overriding assets.
- `scripts/`: `build.py`, `check_links.py`, `convert_images.py`, `serve.py`. Scripts read `SRC`/`DIST` module paths; tests point them at `tmp_path` (`tests/conftest.py`).

## Conventions and gotchas

- Code comments, docstrings, CLI messages and docs are English; only `README.hu.md` is Hungarian. `README.md` and `README.hu.md` change together.
- Sample content stays fictional: `*.example.com`, `Example …` names, generated images. No real businesses, people or contact details.
- Templates autoescape HTML and use `StrictUndefined`; optional page variables need `| default(...)` or a global.
- Shared templates link with `link(domain, path)` and `asset(path)`; never hard-code another site's domain.
- Exactly one `<h1>` per page; every `<img>` has a meaningful `alt` (`alt=""` only for decoration).
- Add a class to `IMG_SIZES` only if its CSS gives the image a definite width (see README, Images).
- Convert new images with `scripts/convert_images.py`; the site favicon overrides the shared one through the same path (`img/favicon.webp`).
- Front-end libraries and fonts are self-hosted; record every addition in the folder's `LICENSES.md`.
- After a design change, run `make preview` and commit `docs/preview.png`.
- Sample images are generated placeholders; their `alt` starts with "Placeholder image:".

## Release and docs

- `tools/check.sh` runs pytest, `ruff check`, `ruff format --check`, the build and the internal link check; CI (`.github/workflows/ci.yml`) runs the same script on Python 3.14 on every push and pull request; keep it green. Run `./setup-hooks.sh` once after cloning: it enables the pre-commit secret guard (`tools/hooks/`).
- Docs change in the same commit as the code: `README.md` and `README.hu.md` (user-facing), `CHANGELOG.md` `## [Unreleased]`.
- Version lives only in `pyproject.toml`. A finished milestone: bump it (SemVer), move Unreleased to `## [x.y.z] - YYYY-MM-DD`, commit, then `git tag -a vX.Y.Z -m "<milestone>"` on that commit. The user pushes with `git push --follow-tags`.
- License: MIT (`LICENSE`). Dependabot: not used.
