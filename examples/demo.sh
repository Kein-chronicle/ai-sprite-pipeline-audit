#!/usr/bin/env bash
cd "$(dirname "$0")/.."
run() { printf '$ %s\n' "$*"; "$@"; printf '[exit %s]\n\n' "$?"; }
tmp=.demo-tmp; rm -rf "$tmp"; mkdir -p "$tmp/production" "$tmp/raw"; trap 'rm -rf "$tmp"' EXIT
python3 - "$tmp" <<'PY'
import hashlib, json, os, sys
from PIL import Image, ImageDraw
root = sys.argv[1]
master = os.path.join(root, "master.png"); Image.new("RGB", (64, 64), (1, 2, 3)).save(master)
lock = {"style_authority": "master.png", "masters": {"H01": {"path": "master.png", "sha256": hashlib.sha256(open(master, "rb").read()).hexdigest(), "width": 64, "height": 64}}}
outs = []
for name, seed in (("a.png", 0), ("b.png", 3)):
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0)); ImageDraw.Draw(img).ellipse([6 + seed, 6, 24, 24], fill=(200, 50, 50, 255))
    img.save(os.path.join(root, "raw", name)); outs.append("raw/" + name)
manifest = {"style_authority": "master.png", "frames": [{"id": "A", "output": outs[0]}, {"id": "B", "output": outs[1]}]}
json.dump(manifest, open(os.path.join(root, "production/manifest.json"), "w")); json.dump(lock, open(os.path.join(root, "production/master-lock.json"), "w"))
open(os.path.join(root, "ledger.jsonl"), "w").write("\n".join(json.dumps({"output": o}) for o in outs) + "\n")
# a flat light backdrop around a blue figure with a white "eye" that must stay opaque
im = Image.new("RGB", (100, 100), (245, 245, 245)); dr = ImageDraw.Draw(im)
dr.ellipse([20, 20, 80, 80], fill=(30, 60, 160)); dr.ellipse([42, 42, 58, 58], fill=(250, 250, 250)); im.save(os.path.join(root, "hero.png"))
PY
echo "# 1. A complete, consistent production passes"
run python3 scripts/audit_production.py "$tmp"
echo "# 2. Someone quietly swaps the style master after frames were generated from it"
printf 'tampered' > "$tmp/master.png"
run python3 scripts/audit_production.py "$tmp"
echo "# 3. Remove a plain light backdrop; the enclosed white eye stays opaque, the original is kept"
run python3 scripts/key_background.py "$tmp/hero.png"
python3 -c "
from PIL import Image
im = Image.open('$tmp/hero.png').convert('RGBA'); print('corner alpha', im.getpixel((2, 2))[3], '| eye alpha', im.getpixel((50, 50))[3])"
ls "$tmp" | grep prekey
