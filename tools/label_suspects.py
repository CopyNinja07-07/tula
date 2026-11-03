"""List hand labels that are probably typing slips, for a person to check.

A label is suspect when Reader A and Muse Glimmer agree with each other on a
photo (foggy or its clear twin) but not with the label. Nothing is changed:
the list is for a human to look at.

Run: PYTHONPATH=src .venv/bin/python tools/label_suspects.py
Writes experiments/results/label_suspects.csv
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"


def clean(s):
    return "".join(ch for ch in (s or "").upper() if ch.isalnum())


def main() -> None:
    a = {r["file"]: clean(r["read"]) for r in csv.DictReader(open(RES / "reader_a_sam31_reads.csv"))}
    g = {}
    for line in open(RES / "glimmer_reads.jsonl"):
        r = json.loads(line)
        g[r["file"]] = clean((r.get("read") or {}).get("plate_text"))
    labels = {r["id"]: r for r in csv.DictReader(open(ROOT / "data" / "labels" / "foggy_labels.csv"))}
    rows = []
    for pid, lab in labels.items():
        if lab["unreadable"] == "true":
            continue
        truth = clean(lab["plate"])
        votes = [v for v in (a.get(f"foggy/{pid}.png"), g.get(f"foggy/{pid}.png"),
                             a.get(f"clear/{pid}.jpg"), g.get(f"clear/{pid}.jpg")) if v]
        best = max(set(votes), key=votes.count) if votes else ""
        if best and best != truth and votes.count(best) >= 2:
            rows.append({"id": pid, "label": truth, "readers_say": best, "votes": votes.count(best),
                         "photo": f"data/raw/foggy_hazy_plates_mendeley/New Hazy dataset/{pid}.png"})
    with open(RES / "label_suspects.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "label", "readers_say", "votes", "photo"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} suspect labels -> {RES / 'label_suspects.csv'}")


if __name__ == "__main__":
    main()
