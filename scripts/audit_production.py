#!/usr/bin/env python3
"""ai-sprite-production-audit: machine-check a generated-sprite production against its contract.
usage: audit_production.py ROOT [--allow-incomplete]     exit 0 ok | 1 failures | 2 bad input
ROOT/production/master-lock.json : {"style_authority": path, "masters": {id: {"path","sha256","width","height"}}}
ROOT/production/manifest.json    : {"style_authority": path, "frames": [{"id","output"}]}
ROOT/ledger.jsonl                : one JSON line per generation event: {"output": path, "sha256": hash of that file (recommended), "prompt":..., "model":...}
Checks: the approved style master still has its checksum/size (nobody swapped it); manifest points at the same style authority; every frame exists,
has a ledger event (no unrecorded generations; if the event records a sha256 it must equal the file's, otherwise a WARN says the content is not pinned),
is RGBA with real transparency (enough fully transparent pixels, a transparent border, no semi-transparent haze), and is not a byte-duplicate of another frame.
Zero existing frames, an empty master lock or a missing style authority are failures, never a pass. --require-ledger-hash turns the WARN into a failure."""
import argparse, hashlib, json, sys
from pathlib import Path
try: from PIL import Image
except ImportError: print("UNMEASURED: Pillow missing"); sys.exit(3)

ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--allow-incomplete", action="store_true"); ap.add_argument("--require-ledger-hash", action="store_true")
ap.add_argument("--min-transparent", type=float, default=0.05, help="least share of fully transparent pixels a sprite frame must have"); a = ap.parse_args()
R = Path(a.root).resolve(); errs = []
def root_file(value):
    """Untrusted manifest paths must stay inside ROOT, without symlink components."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("path must be a nonempty relative POSIX path")
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("absolute paths and parent traversal are forbidden")
    p = R
    for part in rel.parts:
        p = p / part
        if p.is_symlink(): raise ValueError("symlink paths are forbidden")
    if not p.resolve().is_relative_to(R): raise ValueError("path escapes ROOT")
    if p.exists() and not p.is_file(): raise ValueError("path must name a regular file")
    return p
if not 0 <= a.min_transparent <= 1: ap.error("--min-transparent must be finite and between 0 and 1")
def fail(m): errs.append(m); print("FAIL", m)
try:
    manifest = json.loads(root_file("production/manifest.json").read_text()); lock = json.loads(root_file("production/master-lock.json").read_text())
except Exception as e: print(f"bad input: {e}"); sys.exit(2)
if not isinstance(manifest, dict) or not isinstance(lock, dict) or not isinstance(manifest.get("frames"), list) or not manifest["frames"]: print("manifest has no frames (or is malformed): nothing is measured"); sys.exit(2)
if not isinstance(lock.get("masters"), dict) or not lock["masters"]: print("master lock pins no masters: nothing prevents the style reference from being swapped"); sys.exit(2)
if not lock.get("style_authority"): print("master lock names no style_authority"); sys.exit(2)
if manifest.get("style_authority") != lock.get("style_authority"): fail("manifest style authority differs from the master lock")
if str(lock.get("style_authority")) not in {str(m.get("path")) for m in lock["masters"].values() if isinstance(m, dict)}:
    fail("style_authority is not one of the pinned masters: the reference that defines the style is not protected by a checksum")
try: [m["path"] and m["sha256"] and m["width"] and m["height"] for m in lock["masters"].values()]
except (KeyError, TypeError): print("each master needs path, sha256, width and height"); sys.exit(2)
for cid, m in lock["masters"].items():
    try: p = root_file(m["path"])
    except ValueError as e: fail(f"{cid}: invalid master path ({e})"); continue
    if not p.is_file(): fail(f"{cid}: approved master missing"); continue
    if hashlib.sha256(p.read_bytes()).hexdigest() != m["sha256"]: fail(f"{cid}: approved master checksum changed (the style reference must be immutable)")
    try:
        with Image.open(p) as im:
            if im.size != (m["width"], m["height"]): fail(f"{cid}: approved master dimensions changed")
    except Exception as e: fail(f"{cid}: approved master is not a readable image ({type(e).__name__})")
ledger = {}
try: lp = root_file("ledger.jsonl")
except ValueError as e: print(f"bad ledger path: {e}"); sys.exit(2)
if lp.is_file():
    for n, line in enumerate(lp.read_text().splitlines(), 1):
        try:
            ev = json.loads(line)
            if not isinstance(ev, dict): fail(f"ledger line {n}: not a JSON object"); continue
            ledger[ev.get("output")] = ev.get("sha256")
        except json.JSONDecodeError as e: fail(f"ledger line {n}: invalid JSON {e}")
missing, seen = [], {}
for f in manifest["frames"]:
    try: p = root_file(f["output"])
    except ValueError as e: fail(f"invalid frame path ({e})"); continue
    if not p.is_file(): missing.append(f["id"]); continue
    if f["output"] not in ledger: fail(f'{f["id"]}: no generation-ledger event (unrecorded or hand-edited output)')
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if f["output"] in ledger:
        pinned = ledger[f["output"]]
        if pinned and str(pinned).lower() != h: fail(f'{f["id"]}: file content differs from the ledger sha256 (edited after generation)')
        elif not pinned:
            if a.require_ledger_hash: fail(f'{f["id"]}: ledger event has no sha256 (content is not pinned)')
            else: print(f'WARN {f["id"]}: ledger event has no sha256, so a hand-edited file would not be detected')
    if h in seen: fail(f'{f["id"]}: exact duplicate of {seen[h]}')
    else: seen[h] = f["id"]
    try:
        with Image.open(p) as im:
            if im.mode != "RGBA": fail(f'{f["id"]}: mode {im.mode}, expected RGBA'); continue
            al = im.getchannel("A"); hist = al.histogram(); total = im.width * im.height
            if al.point(lambda v: 255 if v > 16 else 0).getbbox() is None: fail(f'{f["id"]}: empty alpha (nothing visible)')
            else:
                clear = sum(hist[:17]) / total; haze = sum(hist[17:255]) / total
                raw = al.tobytes(); w_ = im.width; edge = raw[:w_] + raw[-w_:] + raw[0::w_] + raw[w_ - 1::w_]
                opaque_border = sum(1 for v in edge if v > 240) / len(edge)
                if clear < a.min_transparent: fail(f'{f["id"]}: only {clear:.1%} of pixels are transparent (need {a.min_transparent:.0%}): a backdrop is baked in')
                elif opaque_border > 0.5: fail(f'{f["id"]}: {opaque_border:.0%} of the border is opaque (backdrop baked in, or the subject is cropped)')
                if haze > 0.10: fail(f'{f["id"]}: {haze:.0%} of pixels are semi-transparent (haze around or behind the subject)')
    except Exception as e: fail(f'{f["id"]}: unreadable {e}')
if len(missing) == len(manifest["frames"]): fail("no frame exists on disk: nothing was measured")
elif missing and not a.allow_incomplete: fail(f"missing frames {len(missing)}/{len(manifest['frames'])}")
print(json.dumps({"expected": len(manifest["frames"]), "present": len(manifest["frames"]) - len(missing), "errors": len(errs)}))
sys.exit(1 if errs else 0)
