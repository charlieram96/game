#!/usr/bin/env python3
"""Packages the Godot web export for sharing.

Takes the plain export in build/web/ and writes build/web-dist/: the engine
(.wasm) and game data (.pck) are gzipped (about 45 MB -> 15 MB) and the page
is told to inflate them in the browser (see export/web/shell.html). The
result works on any static host (itch.io, GitHub Pages, a plain web server)
and is also zipped to build/dist/wildbound-web.zip for an itch.io upload.

Files the loading page itself shows (the key art behind the progress bar)
live in export/web/ beside the shell and are copied next to index.html. That
folder is outside the Godot project (export/.gdignore), so they are never
imported into the game or packed into index.pck.

Usage: python3 tools/package_web.py [export_dir] [out_dir]
"""
import gzip
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = "[/*WB_GZ*/]"
COMPRESS = ("index.wasm", "index.pck")
SHELL_DIR = ROOT / "export" / "web"
PAGE_ASSETS = ("keyart.png",)  # loaded by export/web/shell.html, next to index.html


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "web"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build" / "web-dist"
    page = src / "index.html"
    if not page.exists():
        print(f"error: no web export at {src} (run the 'Web' export preset first)")
        return 1
    html = page.read_text(encoding="utf-8")
    if MARKER not in html:
        print("error: index.html has no gzip marker; was it exported with export/web/shell.html?")
        return 1
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in sorted(src.iterdir()):
        if f.is_dir() or f.suffix == ".import" or f.name == "index.html":
            continue
        if f.name in COMPRESS:
            with open(f, "rb") as fin, gzip.GzipFile(out / (f.name + ".gz"), "wb", compresslevel=9, mtime=0) as fout:
                shutil.copyfileobj(fin, fout)
        else:
            shutil.copy2(f, out / f.name)
    for name in PAGE_ASSETS:
        asset = SHELL_DIR / name
        if asset.exists():
            shutil.copy2(asset, out / name)
        else:
            print(f"warning: {asset} is missing; the loading page shows its plain gradient")
    listed = ", ".join(f'"{n}"' for n in COMPRESS)
    (out / "index.html").write_text(html.replace(MARKER, f"[{listed}]"), encoding="utf-8")

    dist = ROOT / "build" / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    archive = dist / "wildbound-web.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f.name)
    total = sum(f.stat().st_size for f in out.iterdir())
    for f in sorted(out.iterdir()):
        print(f"  {f.name:34s} {f.stat().st_size / 1e6:7.2f} MB")
    print(f"web build: {out} ({total / 1e6:.1f} MB)  zip: {archive} ({archive.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
