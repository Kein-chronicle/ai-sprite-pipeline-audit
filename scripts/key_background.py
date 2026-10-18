#!/usr/bin/env python3
"""Turn an edge-connected light neutral generated background into real alpha. Interior whites (eyes, highlights) are enclosed by outlines,
so only pixels reachable from the image border are removed. The original is kept once as <name>.prekey.png. Refuses to remove too little/too much.
usage: key_background.py image.png [...]   (exit 1 if any image was refused or failed; the others are still processed. *.prekey.png backups are skipped.)"""
import os, shutil, stat, sys, tempfile
from collections import deque
from pathlib import Path
from PIL import Image

def candidate(px, lo_min=185, spread=22):
    r, g, b = px[:3]; return min(r, g, b) >= lo_min and max(r, g, b) - min(r, g, b) <= spread

def key(path, lo_min=185, spread=22):
    path = Path(path)
    path = path.parent.resolve() / path.name
    original = path.with_name(path.stem + ".prekey.png")
    if path.suffix.lower() != ".png": raise SystemExit(f"refused: {path} is not a .png (the keyed result is PNG data with an alpha channel)")
    if path.name.endswith(".prekey.png"): print(f"skipped {path}: it is a backup"); return
    # Reject links in both the source and backup paths, including dangling links.
    for candidate_path in (path, original):
        if any(part.is_symlink() for part in (candidate_path, *candidate_path.parents)):
            raise ValueError("symlink input/backup paths are forbidden")
    if original.exists() and not original.is_file(): raise ValueError("backup must be a regular file")
    with path.open("rb") as source, Image.open(source) as opened:
        im = opened.convert("RGBA")
    w, h = im.size; pix = im.load(); seen = bytearray(w * h); q = deque()
    for x in range(w): q.append((x, 0)); q.append((x, h - 1))
    for y in range(h): q.append((0, y)); q.append((w - 1, y))
    removed = 0
    while q:
        x, y = q.popleft(); i = y * w + x
        if seen[i]: continue
        seen[i] = 1
        if not candidate(pix[x, y], lo_min, spread): continue
        r, g, b, _ = pix[x, y]; pix[x, y] = (r, g, b, 0); removed += 1
        if x: q.append((x - 1, y))
        if x + 1 < w: q.append((x + 1, y))
        if y: q.append((x, y - 1))
        if y + 1 < h: q.append((x, y + 1))
    if removed < w * h * 0.05: raise SystemExit(f"refused: removed too little background ({removed}/{w*h}) - not a light plain backdrop?")
    if removed > w * h * 0.95: raise SystemExit(f"refused: removed too much ({removed}/{w*h}) - the subject is light-coloured and open")
    # Exclusive creation does not follow a backup symlink inserted after the check.
    try: backup_fd = os.open(original, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        if original.is_symlink() or not original.is_file(): raise ValueError("unsafe existing backup")
    else:
        with os.fdopen(backup_fd, "wb") as backup, path.open("rb") as source:
            shutil.copyfileobj(source, backup); backup.flush(); os.fsync(backup.fileno())
    # Complete the PNG before replacing the source directory entry. A final-path link
    # inserted concurrently is replaced, not followed. Parent directories must be trusted.
    fd, temporary = tempfile.mkstemp(prefix=".key-background-", suffix=".png", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            im.save(output, format="PNG"); output.flush(); os.fsync(output.fileno())
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    print(f"keyed {path}: transparent={removed}/{w*h}")

if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    failed = 0
    for p in sys.argv[1:]:                                       # one refusal must not abort the rest of the batch
        try: key(p)
        except SystemExit as e: print(e); failed += 1
        except Exception as e: print(f"error: {p}: {type(e).__name__}: {e}"); failed += 1
    sys.exit(1 if failed else 0)
