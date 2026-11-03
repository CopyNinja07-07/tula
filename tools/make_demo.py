"""Build the TULA demo page: real photos in, charge / hold / review out.

Picks a spread of test passages from one calibration split (every scenario,
every photo set, all three decisions), draws SAM 3.1's plate and vehicle
boxes on each photo, and writes docs/demo/demo_data.js next to index.html.

Run: PYTHONPATH=src .venv/bin/python tools/make_demo.py [--per 4]
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

from tula.note import evidence_note
from tula.real_bench import RES, demo_cases, load_photos

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "raw" / "kaggle_bundle"
OUT = ROOT / "docs" / "demo" / "demo_data.js"


def parse_box(s):
    return tuple(int(v) for v in s.strip("()").split(",")) if s else None


def thumb(path: Path, plate_box, vehicle_box) -> str:
    img = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(img)
    w = max(2, img.width // 250)
    if vehicle_box:
        d.rectangle(vehicle_box, outline=(250, 200, 40), width=w)
    if plate_box:
        d.rectangle(plate_box, outline=(40, 220, 120), width=w + 1)
    img.thumbnail((720, 480))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=3, help="cases per (set, decision)")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--glimmer", default=str(RES / "glimmer_reads.jsonl"))
    args = ap.parse_args()
    gpath = Path(args.glimmer)
    photos = load_photos(gpath)
    cases = demo_cases(photos, args.alpha, seed=7)
    boxes = {r["file"]: r for r in csv.DictReader(open(RES / "sam31_boxes.csv"))}
    glim = {json.loads(l)["file"]: json.loads(l) for l in open(gpath)}

    rng = random.Random(3)
    rng.shuffle(cases)
    picked, seen = [], {}
    # Prefer the interesting cases: problems planted, readers wrong, or a held/reviewed passage.
    cases.sort(key=lambda c: (c["scenario"] == "clean" and c["decision"] == "charge"))
    for c in cases:
        key = (c["group"], c["decision"], c["scenario"] != "clean")
        if seen.get(key, 0) < args.per:
            seen[key] = seen.get(key, 0) + 1
            picked.append(c)

    out = []
    for c in picked:
        p = c["photo"]
        b = boxes.get(p["file"], {})
        g = glim.get(p["file"], {})
        gread = g.get("read") or {}
        sig = c["fused_signals"]
        note = evidence_note(c["decision"], sig, p["a"]["plate_text"], p["b"]["plate_text"], None,
                             c["group"], c["certified"], gread.get("image_issues"))
        out.append({
            "file": p["file"], "set": p["set"], "scenario": c["scenario"], "truth": p["truth"],
            "img": thumb(BUNDLE / p["file"], parse_box(b.get("plate_box")), parse_box(b.get("vehicle_box"))),
            "sam_plate": float(b["plate_score"]) if b.get("plate_score") else None,
            "a": p["a"], "b": {**p["b"], "image_issues": gread.get("image_issues", [])},
            "registry": p["reg"], "signals": {k: round(v, 2) for k, v in sig.items()},
            "score": round(c["fused_l"][0], 3), "tau": c["tau"][0] if c["tau"] else None,
            "decision": c["decision"], "wrong_if_charged": c["fused_l"][1],
            "naive_wrong": c["naive"], "note": note,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    summary = json.loads((RES / f"real_bench_alpha{args.alpha}.json").read_text()) \
        if (RES / f"real_bench_alpha{args.alpha}.json").exists() else None
    OUT.write_text("window.TULA_DEMO = " + json.dumps({"cases": out, "alpha": args.alpha,
                                                        "summary": summary}) + ";\n")
    print(f"{len(out)} demo cases -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
