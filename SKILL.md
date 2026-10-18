---
name: ai-sprite-production-audit
description: Control quality and consistency when mass-producing game characters/sprites with image generators - hash-pinned style master ("only one reference defines the style"), generation ledger, manifest of every action x direction x frame, RGBA/transparency/duplicate checks, atlas grid and baseline contracts, and edge-connected background keying that keeps interior whites. Use when producing hundreds of AI-generated frames for a cast of characters, when styles drift between characters, or when generated PNGs have baked-in backdrops.
---

# ai-sprite-production-audit

A production design for keeping a many-frame, multi-character sprite set coherent. Items 1-5 are checked by the scripts here; items 6-8 are design guidance you implement yourself:

1. **One style authority.** A single approved master sheet defines the whole line's style. Characters share layout, proportions, camera, lighting, background and file names.
   `production/master-lock.json` pins each approved master by **sha256 + dimensions**; the audit fails if one changes (nobody quietly "improves" the reference).
2. **Contract before generation** (a file you write; the scripts do not read it): `contract.json` (raw frame size, output sizes, atlas max size, background = transparent, directions, per-character identity and signature behaviours).
   A **manifest** enumerates every `character x action x direction x frame` with its output path - missing = measurable.
3. **Generation ledger** (JSONL): every generation event records output path, `sha256` of the output, prompt and model. A frame without a ledger line is an unrecorded output -> fail; a line whose `sha256` no longer matches is an edited frame -> fail; a line without `sha256` only warns (`--require-ledger-hash` fails it).
4. **Per-frame checks** (`scripts/audit_production.py`): file exists; ledger event exists and matches; RGBA; alpha not empty; at least `--min-transparent` (5 %) fully transparent pixels and a mostly transparent border (no baked backdrop);
   no more than 10 % semi-transparent haze; no byte-duplicate frames. An empty master lock, a missing style authority or zero existing frames fail.
5. **Background keying** (`scripts/key_background.py`): generators love light-neutral backdrops. Remove only pixels connected to the **border** (flood fill) so
   interior whites (eyes, highlights) survive; keep the original once as `.prekey.png` (only after the checks pass); refuse if it removed < 5 % (not a plain backdrop) or > 95 % (light open subject). Only `.png` files are accepted, and `*.prekey.png` backups are skipped, so `raw/*.png` is safe to re-run.
6. **Atlas contracts** (not implemented here; implement them for your packer): page size cap; every slice on a grid and equal to the cell size; slice inside the page;
   no opaque pixel touching the cell edge (clipping); **ground baseline spread <= 2 px** for grounded animations; equivalent visible-mass ratio between frames of one
   animation <= ~1.45 (pops in size); no duplicate source frames in an animation; every animation has a scene + description; minimum 3 frames (6+ for walk/run), 8 directions.
7. Style rules that fight "average AI output": asymmetry in a shared garment, high-contrast colour fields, forbid reinterpretation (e.g. don't pixel-art a painted style).

```bash
python3 scripts/key_background.py raw/*.png
python3 scripts/audit_production.py ROOT [--allow-incomplete]
python3 tests/run.py
```
Image-generation CLIs and image content policies change; keep prompts per character in a versioned doc, and every generation in the ledger.

Runtime dependency: install `requirements.txt` with `python3 -m pip install -r requirements.txt`. Pillow must be at least 12.3.0; optional model dependencies listed above are separate.

Security boundary: manifest/master/ledger files and referenced images must use paths inside ROOT; absolute paths, parent traversal and symlink components are rejected. Background keying rejects source/backup symlinks, creates backups exclusively, and completes a temporary PNG before replacing the source. The caller must trust the selected ROOT/input parent directory and prevent concurrent modification by another process; these scripts are not a filesystem sandbox. Existing regular backups are retained, not overwritten.
