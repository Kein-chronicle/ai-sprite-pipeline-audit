import hashlib, json, os, subprocess, sys, tempfile, shutil
from PIL import Image, ImageDraw
H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"); ok = True
def run(script, *a): p = subprocess.run([sys.executable, os.path.join(H, script), *a], capture_output=True, text=True); return p.returncode, p.stdout + p.stderr
def expect(n, c, v=""):
    global ok; ok &= bool(c); print(("ok   " if c else "FAIL ") + n + ("" if c else f"\n     {v}"))

# ---- background keying
d = tempfile.mkdtemp(); p = os.path.join(d, "hero.png")
im = Image.new("RGB", (100, 100), (245, 245, 245)); dr = ImageDraw.Draw(im)
dr.ellipse([20, 20, 80, 80], fill=(30, 60, 160)); dr.ellipse([42, 42, 58, 58], fill=(250, 250, 250))       # white "eye" enclosed by the body
im.save(p); rc, out = run("key_background.py", p)
k = Image.open(p).convert("RGBA")
expect("border-connected backdrop becomes transparent", rc == 0 and k.getpixel((2, 2))[3] == 0, out)
expect("enclosed white (the eye) is kept opaque", k.getpixel((50, 50))[3] == 255)
expect("original preserved as .prekey.png", os.path.exists(os.path.join(d, "hero.prekey.png")))
q = os.path.join(d, "dark.png"); Image.new("RGB", (50, 50), (20, 20, 20)).save(q); rc, out = run("key_background.py", q)
expect("a non-light backdrop is refused (nothing removed)", rc != 0 and "too little" in out, out)

# ---- production audit
root = tempfile.mkdtemp(); os.makedirs(os.path.join(root, "production")); os.makedirs(os.path.join(root, "raw"))
master = os.path.join(root, "master.png"); Image.new("RGB", (64, 64), (1, 2, 3)).save(master)
lock = {"style_authority": "master.png", "masters": {"H01": {"path": "master.png", "sha256": hashlib.sha256(open(master, "rb").read()).hexdigest(), "width": 64, "height": 64}}}
def frame(name, kind="ok", seed=0):
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    if kind == "ok": ImageDraw.Draw(img).ellipse([6 + seed, 6, 24, 24], fill=(200, 50, 50, 255))
    if kind == "opaque": img = Image.new("RGBA", (32, 32), (9, 9, 9, 255))
    if kind == "empty": pass
    if kind == "rgb": img = Image.new("RGB", (32, 32), (9, 9, 9))
    img.save(os.path.join(root, "raw", name)); return f"raw/{name}"
outs = [frame("a.png", seed=0), frame("b.png", seed=3)]
man = {"style_authority": "master.png", "frames": [{"id": "A", "output": outs[0]}, {"id": "B", "output": outs[1]}]}
def write(m=man, l=lock, ledger=outs):
    json.dump(m, open(os.path.join(root, "production/manifest.json"), "w")); json.dump(l, open(os.path.join(root, "production/master-lock.json"), "w"))
    open(os.path.join(root, "ledger.jsonl"), "w").write("\n".join(json.dumps({"output": o}) for o in ledger) + "\n")
write(); rc, out = run("audit_production.py", root); expect("a clean production passes", rc == 0, out)
write(ledger=outs[:1]); rc, out = run("audit_production.py", root); expect("frame without a ledger event is flagged", rc == 1 and "ledger" in out, out)
write(); open(master, "wb").write(b"tampered"); rc, out = run("audit_production.py", root); expect("a swapped style master is detected (checksum) without a crash", rc == 1 and "checksum changed" in out and "Traceback" not in out, out)
Image.new("RGB", (64, 64), (1, 2, 3)).save(master)
shutil.copy(os.path.join(root, "raw/a.png"), os.path.join(root, "raw/dup.png")); man2 = json.loads(json.dumps(man)); man2["frames"].append({"id": "D", "output": "raw/dup.png"})
write(man2, ledger=outs + ["raw/dup.png"]); rc, out = run("audit_production.py", root); expect("byte-duplicate frame is flagged", rc == 1 and "duplicate" in out, out)
bad = [frame("o.png", "opaque"), frame("e.png", "empty"), frame("r.png", "rgb")]
man3 = {"style_authority": "master.png", "frames": [{"id": "O", "output": bad[0]}, {"id": "E", "output": bad[1]}, {"id": "R", "output": bad[2]}]}
write(man3, ledger=bad); rc, out = run("audit_production.py", root)
expect("baked backdrop / empty alpha / RGB mode are each flagged", all(s in out for s in ["backdrop is baked in", "empty alpha", "expected RGBA"]), out)
man4 = json.loads(json.dumps(man)); man4["frames"].append({"id": "Z", "output": "raw/missing.png"}); write(man4, ledger=outs)
rc, out = run("audit_production.py", root); expect("missing frames fail by default", rc == 1 and "missing frames" in out, out)
rc, out = run("audit_production.py", root, "--allow-incomplete"); expect("--allow-incomplete tolerates missing frames", rc == 0, out)

# --- review findings: each of these used to pass
write(); 
def solo(img, name="solo.png"):
    p = os.path.join(root, "raw", name); img.save(p); return p
grey = Image.new("RGBA", (32, 32), (128, 128, 128, 255)); grey.putpixel((0, 0), (0, 0, 0, 0)); p = solo(grey)
man3 = {"style_authority": "master.png", "frames": [{"id": "G", "output": "raw/solo.png"}]}
def audit_with(m, ledger_lines=None, extra=()):
    json.dump(m, open(os.path.join(root, "production/manifest.json"), "w"))
    open(os.path.join(root, "ledger.jsonl"), "w").write("\n".join(json.dumps(x) if not isinstance(x, str) else x for x in (ledger_lines or [])) + "\n")
    return run("audit_production.py", root, *extra)
rc, out = audit_with(man3, [{"output": "raw/solo.png"}]); expect("an opaque grey backdrop with ONE transparent pixel is flagged", rc == 1 and "backdrop is baked in" in out, out)
haze = Image.new("RGBA", (32, 32), (255, 255, 255, 60)); ImageDraw.Draw(haze).ellipse([8, 8, 24, 24], fill=(200, 50, 50, 255)); solo(haze)
rc, out = audit_with(man3, [{"output": "raw/solo.png"}]); expect("a 60-alpha haze backdrop around an opaque subject is flagged", rc == 1 and ("semi-transparent" in out or "baked in" in out), out)
good = Image.new("RGBA", (32, 32), (0, 0, 0, 0)); ImageDraw.Draw(good).ellipse([8, 8, 24, 24], fill=(200, 50, 50, 255)); gp = solo(good)
h = hashlib.sha256(open(gp, "rb").read()).hexdigest()
rc, out = audit_with(man3, [{"output": "raw/solo.png", "sha256": h}]); expect("a ledger sha256 that matches passes without a warning", rc == 0 and "WARN" not in out, out)
rc, out = audit_with(man3, [{"output": "raw/solo.png", "sha256": "0" * 64}]); expect("a ledger sha256 that does not match is an edited frame", rc == 1 and "ledger sha256" in out, out)
rc, out = audit_with(man3, [{"output": "raw/solo.png"}], ["--require-ledger-hash"]); expect("--require-ledger-hash fails an unpinned ledger event", rc == 1, out)
rc, out = audit_with(man3, ["[1]", {"output": "raw/solo.png", "sha256": h}]); expect("a ledger line that is not an object is reported, not a crash", rc == 1 and "Traceback" not in out, out)
json.dump({"style_authority": "master.png", "masters": {}}, open(os.path.join(root, "production/master-lock.json"), "w"))
rc, out = audit_with(man3, [{"output": "raw/solo.png", "sha256": h}]); expect("an empty master lock is exit 2", rc == 2, out)
json.dump(lock, open(os.path.join(root, "production/master-lock.json"), "w"))
os.remove(gp); rc, out = audit_with(man3, [], ["--allow-incomplete"]); expect("--allow-incomplete with every frame missing still fails", rc == 1 and "no frame exists" in out, out)
d2 = tempfile.mkdtemp(); hp = os.path.join(d2, "hero.png"); im2 = Image.new("RGB", (60, 60), (245, 245, 245)); ImageDraw.Draw(im2).ellipse([15, 15, 45, 45], fill=(30, 60, 160)); im2.save(hp)
rc, out = run("key_background.py", hp); rc2, out2 = run("key_background.py", os.path.join(d2, "hero.prekey.png"))
expect("a .prekey.png backup is skipped, not keyed again", "skipped" in out2 and not os.path.exists(os.path.join(d2, "hero.prekey.prekey.png")), out2)
dark = os.path.join(d2, "dark.png"); Image.new("RGB", (30, 30), (20, 20, 20)).save(dark); rc, out = run("key_background.py", dark, hp)
expect("a refused image leaves no stray backup", not os.path.exists(os.path.join(d2, "dark.prekey.png")), out)
jp = os.path.join(d2, "x.jpg"); Image.new("RGB", (30, 30), (245, 245, 245)).save(jp); rc, out = run("key_background.py", jp)
expect("a non-PNG path is refused (no PNG data written into a .jpg)", rc == 1 and "not a .png" in out, out)
lock2 = dict(lock, style_authority="does/not/exist.png"); json.dump(lock2, open(os.path.join(root, "production/master-lock.json"), "w"))
rc, out = audit_with(dict(man3, style_authority="does/not/exist.png"), [{"output": "raw/solo.png", "sha256": h}]); expect("a style authority that is not a pinned master is a failure", rc == 1 and "not one of the pinned masters" in out, out)
json.dump(lock, open(os.path.join(root, "production/master-lock.json"), "w"))
gp2 = solo(good); rc, out = audit_with(man3, [{"output": "raw/solo.png", "sha256": h.upper()}]); expect("an upper-case ledger sha256 is accepted", rc == 0, out)
# Independent adversarial audit: hostile filesystem inputs stay within their boundary.
with tempfile.TemporaryDirectory() as attack:
    from pathlib import Path
    ar = Path(attack) / "root"; (ar / "production").mkdir(parents=True)
    external = Path(attack) / "external.png"
    image = Image.new("RGBA", (16, 16), (0, 0, 0, 0)); ImageDraw.Draw(image).rectangle((4, 4, 11, 11), fill=(1, 2, 3, 255)); image.save(external)
    digest = hashlib.sha256(external.read_bytes()).hexdigest()
    for hostile_path in ("../external.png", str(external), "linked.png"):
        if hostile_path == "linked.png": (ar / hostile_path).symlink_to(external)
        badlock = {"style_authority": hostile_path, "masters": {"M": {"path": hostile_path, "sha256": digest, "width": 16, "height": 16}}}
        badman = {"style_authority": hostile_path, "frames": [{"id": "F", "output": hostile_path}]}
        (ar / "production/master-lock.json").write_text(json.dumps(badlock)); (ar / "production/manifest.json").write_text(json.dumps(badman))
        (ar / "ledger.jsonl").write_text(json.dumps({"output": hostile_path, "sha256": digest}) + "\n")
        rc, out = run("audit_production.py", str(ar), "--require-ledger-hash")
        expect(f"audit rejects external or symlink path {hostile_path}", rc != 0 and "invalid" in out, out)
    hero = ar / "hero.png"; image = Image.new("RGB", (16, 16), (245, 245, 245)); ImageDraw.Draw(image).rectangle((4, 4, 11, 11), fill=(1, 2, 3)); image.save(hero)
    before = hero.read_bytes(); backup = ar / "hero.prekey.png"; victim = Path(attack) / "outside-new.png"; backup.symlink_to(victim)
    rc, out = run("key_background.py", str(hero))
    expect("dangling backup link is refused without touching source or outside file", rc != 0 and not victim.exists() and hero.read_bytes() == before, out)
    backup.unlink(); linked = ar / "linked-input.png"; linked.symlink_to(hero)
    rc, out = run("key_background.py", str(linked))
    expect("source symlink is refused without touching target", rc != 0 and hero.read_bytes() == before, out)
    rc, out = run("key_background.py", str(hero))
    expect("normal keying after attacks retains exact original backup", rc == 0 and backup.read_bytes() == before and hero.read_bytes() != before, out)
    for threshold in ("nan", "inf", "-1", "2"):
        rc, out = run("audit_production.py", str(ar), "--min-transparent", threshold)
        expect(f"invalid transparency threshold {threshold} rejected", rc == 2 and "--min-transparent" in out, out)
sys.exit(0 if ok else 1)

