"""Convert and downscale images for the web.

- AVIF, JPG, PNG -> WebP (rotated by EXIF orientation); the original is deleted (--keep: kept).
- Images larger than --max-size (by the longer side) are scaled down proportionally, existing WebPs too.
- Folders are processed recursively; WebPs that are already fine are left alone.

Usage:
  python scripts/convert_images.py src/sites/bakery.example.com/assets/img
  python scripts/convert_images.py src --max-size 1920 --dry-run
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

SOURCE_EXT = {".avif", ".jpg", ".jpeg", ".png"}


def process(p: Path, quality: int, max_size: int, keep: bool, dry_run: bool) -> int:
    """Return value: bytes saved (0 for a dry run)."""
    is_webp = p.suffix.lower() == ".webp"
    try:
        img = Image.open(p)
    except OSError as e:  # includes UnidentifiedImageError
        print(f"Cannot open: {p}: {e}", file=sys.stderr)
        return 0
    too_big = max(img.size) > max_size
    if is_webp and not too_big:
        return 0

    action = ("resize" if too_big else "") + (" + WebP" if not is_webp else "")
    print(f"{p}: {img.size[0]}x{img.size[1]} {action.strip(' +')}")
    if dry_run:
        return 0

    before = p.stat().st_size
    img = ImageOps.exif_transpose(img)
    if too_big:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if has_alpha else "RGB")
    out = p.with_suffix(".webp")
    tmp = out.with_suffix(".tmp.webp")
    img.save(tmp, "WEBP", quality=quality, method=6)
    tmp.replace(out)
    if not is_webp and not keep:
        p.unlink()
    return before - out.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert images to WebP and scale them down.")
    parser.add_argument("paths", nargs="+", type=Path, help="image files or folders (recursive)")
    parser.add_argument("-q", "--quality", type=int, default=82, help="WebP quality 0-100 (default: 82)")
    parser.add_argument("--max-size", type=int, default=1920, help="max. size of the longer side in px (default: 1920)")
    parser.add_argument("--keep", action="store_true", help="keep the original JPG/PNG/AVIF")
    parser.add_argument("--dry-run", action="store_true", help="only print what would happen")
    args = parser.parse_args()

    files: list[Path] = []
    for path in args.paths:
        if path.is_dir():
            files += sorted(f for f in path.rglob("*") if f.suffix.lower() in SOURCE_EXT | {".webp"})
        elif path.is_file():
            files.append(path)
        else:
            print(f"Does not exist: {path}", file=sys.stderr)
            return 1

    saved = sum(process(f, args.quality, args.max_size, args.keep, args.dry_run) for f in files)
    if not args.dry_run:
        print(f"Saved: {saved // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
