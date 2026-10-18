# ai-sprite-pipeline-audit

**Audit a batch of AI-generated sprites: immutable style masters, generation ledger, duplicate frames, real transparency, plus safe background keying.**

[![test](https://github.com/Kein-chronicle/ai-sprite-pipeline-audit/actions/workflows/test.yml/badge.svg)](https://github.com/Kein-chronicle/ai-sprite-pipeline-audit/actions/workflows/test.yml) ![license](https://img.shields.io/badge/license-MIT-blue.svg)

## Why

Batch generation drifts: a style master gets swapped, a frame is hand-edited without a record, a backdrop is baked into the PNG. The audit makes those visible, and the keying script removes a light background without eating enclosed whites such as an eye.

## Install

**As a Claude Code skill** (Claude uses it when the task matches the skill description):

```sh
git clone https://github.com/Kein-chronicle/ai-sprite-pipeline-audit.git ~/.claude/skills/ai-sprite-production-audit
```

For a single project, clone into `<project>/.claude/skills/ai-sprite-production-audit` instead, then start a new Claude Code session.

**As plain scripts:**

```sh
git clone https://github.com/Kein-chronicle/ai-sprite-pipeline-audit.git
cd ai-sprite-pipeline-audit
```

**Requires:** Python 3.10+, Pillow.

Use the security-patched Pillow runtime:

```sh
python3 -m pip install -r requirements.txt
```

## Quick start

Audit a tiny production:

```console
$ bash examples/demo.sh
# 1. A complete, consistent production passes
$ python3 scripts/audit_production.py .demo-tmp
WARN A: ledger event has no sha256, so a hand-edited file would not be detected
WARN B: ledger event has no sha256, so a hand-edited file would not be detected
{"expected": 2, "present": 2, "errors": 0}
[exit 0]

# 2. Someone quietly swaps the style master after frames were generated from it
$ python3 scripts/audit_production.py .demo-tmp
FAIL H01: approved master checksum changed (the style reference must be immutable)
FAIL H01: approved master is not a readable image (UnidentifiedImageError)
WARN A: ledger event has no sha256, so a hand-edited file would not be detected
WARN B: ledger event has no sha256, so a hand-edited file would not be detected
{"expected": 2, "present": 2, "errors": 2}
[exit 1]

# 3. Remove a plain light backdrop; the enclosed white eye stays opaque, the original is kept
$ python3 scripts/key_background.py .demo-tmp/hero.png
keyed /private./.demo-tmp/hero.png: transparent=7091/10000
[exit 0]

corner alpha 0 | eye alpha 255
hero.prekey.png
```

The output above is real: it is produced by the files in `examples/`.

## Use it on your own files

```sh
python3 scripts/audit_production.py ./my-production
python3 scripts/key_background.py sprite1.png sprite2.png
```

Sample inputs for every file format are in `examples/` and `tests/`; the details are in [SKILL.md](SKILL.md).

## What it checks

- `audit_production.py ROOT`: manifest and master lock agree, master checksums unchanged, every frame has a ledger event, no exact duplicates, RGBA with real transparency, no haze.
- `key_background.py image.png`: makes a border-connected light backdrop transparent, keeps the original as `.prekey.png`, refuses non-light backdrops.

## Limits

- Needs Pillow.
- Checks structure, not artistic quality.

## More from the same collection

Small, tested tools that grew out of running AI agents and game/app pipelines for months:

- [**canvas-render-pixel-gate**](https://github.com/Kein-chronicle/canvas-render-pixel-gate): Detect grey-box screenshots: measure unique colors and flat-fill share of a rendered game canvas, and refuse to pass what it could not measure.
- [**web-game-asset-reality-check**](https://github.com/Kein-chronicle/web-game-asset-reality-check): Catch web-game bugs the type checker can't: fonts that are declared but not shipped, runtime CDN dependencies, and page errors from headless Chromium.
- [**ffmpeg-video-qa-gates**](https://github.com/Kein-chronicle/ffmpeg-video-qa-gates): Machine QA for short videos with ffmpeg: frozen frames, dead air, loudness, true peak, size, a busy opening, and readable subtitle timing.

## Development

```sh
python3 tests/run.py
```

The tests include inputs that are supposed to be rejected, so a green run also shows the checks can fail. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).

If this saved you a debugging session, a star helps other people find it. Bug reports and failing test cases are even better.

<sub>Keywords: sprites, game-art, generative-ai, image-generation, pixel-art, audit, pillow, claude-skills</sub>
