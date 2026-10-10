"""Build output: unchanged files, change list and generated meta files."""

import os

import build
import check_links
from conftest import page, write


def test_sync_keeps_unchanged_files_and_their_mtime(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    write(src / "same.txt", "same")
    write(src / "new.txt", "new")
    write(dst / "same.txt", "same")
    write(dst / "gone.txt", "old")
    write(dst / "empty/old.txt", "old")
    os.utime(dst / "same.txt", (1_000_000, 1_000_000))
    build.sync_dir(src, dst)
    assert (dst / "same.txt").stat().st_mtime == 1_000_000
    assert (dst / "new.txt").read_text() == "new"
    assert not (dst / "gone.txt").exists() and not (dst / "empty").exists()


def test_change_lines_list_uploads_and_deletions_per_domain():
    old = {"a.example.com/index.html": "1", "a.example.com/old.html": "2", "b.example.com/index.html": "3"}
    new = {"a.example.com/index.html": "9", "a.example.com/new.html": "4", "b.example.com/index.html": "3"}
    assert build.change_lines(old, new, ["a.example.com", "b.example.com"]) == [
        "== a.example.com",
        "  upload: index.html",
        "  upload: new.html",
        "  delete from server: old.html",
    ]


def test_second_build_without_changes_reports_no_changes(tree):
    build.main(["-q"])
    build.main(["-q"])
    assert (tree / "dist/CHANGED.txt").read_text() == "No changes.\n"


def test_building_one_domain_keeps_the_manifest_of_the_others(tree):
    build.main(["-q"])
    write(tree / "src/sites/b.example.com/pages/index.html", page("Home B2", "<main>B2</main>"))
    build.main(["a.example.com", "-q"])
    build.main(["b.example.com", "-q"])
    assert (tree / "dist/CHANGED.txt").read_text() == "== b.example.com\n  upload: index.html\n  upload: llms.txt\n"


def test_noindex_pages_are_rendered_but_left_out_of_sitemap_and_llms(tree):
    write(tree / "src/sites/a.example.com/pages/thanks.html", page("Thanks", "<main>T</main>", noindex=True))
    build.main(["a.example.com", "-q"])
    dist = tree / "dist/a.example.com"
    assert (dist / "thanks.html").is_file()
    assert "thanks" not in (dist / "sitemap.xml").read_text()
    assert "thanks" not in (dist / "llms.txt").read_text()
    assert "<loc>https://a.example.com/</loc>" in (dist / "sitemap.xml").read_text()


def test_robots_points_to_the_sitemap(tree):
    build.main(["a.example.com", "-q"])
    assert "Sitemap: https://a.example.com/sitemap.xml" in (tree / "dist/a.example.com/robots.txt").read_text()


def test_htaccess_forces_https_and_redirects_old_urls(tree):
    build.main(["a.example.com", "-q"])
    htaccess = (tree / "dist/a.example.com/.htaccess").read_text()
    assert "RewriteRule ^ https://a.example.com%{REQUEST_URI} [L,R=301]" in htaccess
    assert "Redirect 301 /old.html /" in htaccess
    assert "Strict-Transport-Security" in htaccess


def test_llms_txt_lists_pages_with_descriptions(tree):
    build.main(["a.example.com", "-q"])
    llms = (tree / "dist/a.example.com/llms.txt").read_text()
    assert llms.startswith("# Site A\n\n> Description.\n")
    assert "- [Home A](https://a.example.com/): Description." in llms


def test_link_check_passes_on_a_clean_build(tree):
    build.main(["-q"])
    assert check_links.main([]) == 0


def test_link_check_fails_on_a_broken_internal_link(tree, capsys):
    write(
        tree / "src/sites/a.example.com/pages/index.html", page("Home A", '<main><a href="/missing.html">x</a></main>')
    )
    build.main(["-q"])
    assert check_links.main([]) == 1
    assert "a.example.com/index.html: /missing.html (no such file)" in capsys.readouterr().out


def test_link_check_fails_on_http_links_between_own_domains(tree, capsys):
    body = '<main><a href="http://b.example.com/">B</a></main>'
    write(tree / "src/sites/a.example.com/pages/index.html", page("Home A", body))
    build.main(["-q"])
    assert check_links.main([]) == 1
    assert "(needs https instead of http)" in capsys.readouterr().out
