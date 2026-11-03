"""Reader A vs Reader B (Muse Glimmer) on real photos, scored against hand labels.

Scores per reader and per set (foggy, clear, indian):
  exact %         the whole plate right
  CER %           character error rate (edit distance / plate length)
  abstain %       reader said it could not read the plate
  conf-wrong %    of reads the reader was >= 90% sure of, the share that were wrong
                  (the reads that would bill the wrong person if trusted)

Run: PYTHONPATH=src .venv/bin/python tools/compare_readers.py [glimmer_reads.jsonl]
Writes experiments/results/reader_comparison.md and .json.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from tula.evidence import edit_distance

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"
MANIFEST = ROOT / "data" / "raw" / "kaggle_bundle" / "manifest.csv"
SURE = 0.9


def clean(s) -> str:
    return "".join(ch for ch in (s or "").upper() if ch.isalnum())


def score(items: list[dict]) -> dict:
    """items: dicts with truth, read (str or ''), conf (float or None)."""
    n = len(items)
    if not n:
        return {}
    exact = sum(i["read"] == i["truth"] for i in items)
    cer = sum(edit_distance(i["read"], i["truth"]) / max(1, len(i["truth"])) for i in items) / n
    abstain = sum(not i["read"] for i in items)
    sure = [i for i in items if i["conf"] is not None and i["conf"] >= SURE and i["read"]]
    sure_wrong = sum(i["read"] != i["truth"] for i in sure)
    return {"n": n, "exact_pct": round(100 * exact / n, 1), "cer_pct": round(100 * min(cer, 9.99), 1),
            "abstain_pct": round(100 * abstain / n, 1), "sure_n": len(sure),
            "sure_wrong": sure_wrong,
            "sure_wrong_pct": round(100 * sure_wrong / len(sure), 1) if sure else None}


def main() -> None:
    manifest = [r for r in csv.DictReader(open(MANIFEST)) if r["unreadable"] != "True"]
    truth = {r["file"]: clean(r["truth"]) for r in manifest}
    per = defaultdict(list)  # (reader, set) -> items

    # Reader A, old crops (pre-filled reads on foggy; zenitsu crops on indian)
    za = {r["id"]: r for r in csv.DictReader(open(RES / "reader_a_zenitsu_reads.csv"))}
    for r in manifest:
        if r["set"] == "indian" and r["id"] in za:
            z = za[r["id"]]
            per[("Reader A (open OCR)", "indian")].append(
                dict(truth=truth[r["file"]], read=clean(z["read"]), conf=float(z["confidence"] or 0)))

    # Reader A on SAM 3.1 crops (foggy, clear)
    for r in csv.DictReader(open(RES / "reader_a_sam31_reads.csv")):
        if r["file"] in truth:
            per[("Reader A on SAM 3.1 crop", r["set"])].append(
                dict(truth=truth[r["file"]], read=clean(r["read"]), conf=float(r["confidence"] or 0)))

    # Reader B: Muse Glimmer
    gpath = Path(sys.argv[1]) if len(sys.argv) > 1 else RES / "glimmer_reads.jsonl"
    if gpath.exists():
        for line in open(gpath):
            g = json.loads(line)
            if g["file"] not in truth:
                continue
            read = g.get("read") or {}
            text = clean(read.get("plate_text")) if read.get("plate_readable", True) else ""
            conf = read.get("plate_confidence")
            per[("Reader B (Muse Glimmer)", g["set"])].append(
                dict(truth=truth[g["file"]], read=text, conf=float(conf) if conf is not None else None))

    table = {f"{k[0]} | {k[1]}": score(v) for k, v in sorted(per.items(), key=lambda kv: (kv[0][1], kv[0][0]))}
    (RES / "reader_comparison.json").write_text(json.dumps(table, indent=2))
    lines = ["| Reader | Set | Photos | Exact | Char. error | Said unreadable | Sure (>=90%) but wrong |",
             "|---|---|---|---|---|---|---|"]
    for key, s in table.items():
        reader, st = key.split(" | ")
        sw = f"{s['sure_wrong']}/{s['sure_n']} ({s['sure_wrong_pct']}%)" if s["sure_n"] else "none sure"
        lines.append(f"| {reader} | {st} | {s['n']} | {s['exact_pct']}% | {s['cer_pct']}% | {s['abstain_pct']}% | {sw} |")
    md = "\n".join(lines)
    (RES / "reader_comparison.md").write_text(
        "# Reader comparison on real photos\n\nTruth = hand labels (foggy, clear) and dataset labels (indian). "
        "Photos marked unreadable by the labeller are left out.\n\n" + md + "\n")
    print(md)


if __name__ == "__main__":
    main()
