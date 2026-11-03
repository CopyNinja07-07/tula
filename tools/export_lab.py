"""Export real calibration and test scores so the website can run the controller live.

For each random split this saves, per passage: group, TULA's doubt score, whether
charging would be wrong, and Glimmer's own confidence (for the one-threshold
comparison). The website then re-runs conformal risk control in the browser for
any promise the viewer picks. Same pipeline as src/tula/real_bench.py.

Run: PYTHONPATH=src .venv/bin/python tools/export_lab.py
Writes docs/lab_data.js
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from tula.evidence import LearnedScore
from tula.real_bench import RES, Registry, load_photos, passage, split_scenes

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ["clear", "foggy", "indian"]


def one_split(photos, seed: int) -> dict:
    rng = random.Random(seed)
    parts = split_scenes(photos, rng)
    reg, by_tag = Registry(rng), {}
    fit = [passage(p, reg, by_tag, rng) for p in parts["fit"] for _ in range(3)]
    cal = [passage(p, reg, by_tag, rng) for p in parts["cal"]]
    test = [passage(p, reg, by_tag, rng) for p in parts["test"] for _ in range(2)]
    model = LearnedScore().fit([c["fused_signals"] for c in fit], [c["fused"][1] for c in fit])

    def rows(cases, extra):
        out = {"g": [], "s": [], "w": []}
        if extra:
            out.update({"bc": [], "bw": [], "nw": []})
        for c in cases:
            out["g"].append(GROUPS.index(c["group"]))
            out["s"].append(round(model.score(c["fused_signals"], c["fused"][2]), 4))
            out["w"].append(int(c["fused"][1]))
            if extra:
                # Glimmer alone: charge when it is sure enough and found someone to bill.
                out["bc"].append(round(c["b_conf"], 3) if c["vlm"][2] else -1)
                out["bw"].append(int(c["vlm"][1]))
                out["nw"].append(int(c["naive"]))
        return out

    return {"cal": rows(cal, False), "test": rows(test, True)}


def main() -> None:
    photos = load_photos(RES / "glimmer_reads.jsonl")
    data = {"groups": GROUPS, "photos": len(photos), "splits": [one_split(photos, s) for s in range(30)]}
    out = ROOT / "docs" / "lab_data.js"
    out.parent.mkdir(exist_ok=True)
    out.write_text("window.TULA_LAB = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"{len(data['splits'])} splits -> {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
