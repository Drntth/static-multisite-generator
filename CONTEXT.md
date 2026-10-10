# static-multisite-generator

Building and uploading several small static websites of one owner from a single source.

## Terms

**site**: One website on its own domain, configured in `src/sites.toml` and stored under `src/sites/<domain>/`.
_Do not confuse with_: page (one HTML document of a site).

**shared layer**: Templates and assets in `src/shared/` used by every site.
_Related_: override.

**override**: A site-specific asset on the same path as a shared one; the site's file wins.

**page**: A template under `src/sites/<domain>/pages/` rendered to one HTML file. Files starting with `_` are partials, not pages.

**noindex page**: A rendered page left out of `sitemap.xml` and `llms.txt`.

**meta files**: The generated `sitemap.xml`, `robots.txt`, `llms.txt` and `.htaccess` of a site.

**manifest**: `dist/manifest.json`, the SHA-256 hash of every output file of the last build.

**change list**: `dist/CHANGED.txt`, the files to upload and to delete per domain since the previous build.
