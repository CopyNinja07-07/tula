"""Pack the labelled plate photos into one folder for a private Kaggle dataset.

Contents:
  foggy/<id>.png   the hand-labelled foggy photos
  clear/<id>.jpg   the clear version of the same scene (resized)
  indian/<n>.png   a fixed random sample of the zenitsu09 Indian plate photos
  manifest.csv     set, file, truth, unreadable, reader_a read

Run: .venv/bin/python tools/make_kaggle_bundle.py [--indian 600]
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import zipfile
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FOG = RAW / "foggy_hazy_plates_mendeley"
OUT = RAW / "kaggle_bundle"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indian", type=int, default=600)
    ap.add_argument("--seed", type=int, default=26)
    args = ap.parse_args()
    for sub in ("foggy", "clear", "indian"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    rows = []

    # Foggy photos: Suryansh's typed labels are the truth; the pre-read is Reader A.
    pre = {r["id"]: r for r in csv.DictReader(open(FOG / "prelabels.csv"))}
    labels = list(csv.DictReader(open(ROOT / "data" / "labels" / "foggy_labels.csv")))
    gt = zipfile.ZipFile(FOG / "Ground_Truth_images.zip")
    gt_names = {Path(n).stem: n for n in gt.namelist() if not n.endswith("/")}
    for r in labels:
        pid = r["id"]
        src = FOG / "New Hazy dataset" / f"{pid}.png"
        Image.open(src).convert("RGB").save(OUT / "foggy" / f"{pid}.png")
        unreadable = r["unreadable"] == "true"
        truth = "" if unreadable else r["plate"].upper()
        rows.append(dict(set="foggy", file=f"foggy/{pid}.png", id=pid, truth=truth,
                         unreadable=unreadable, reader_a=pre.get(pid, {}).get("pre_read", "")))
        if pid in gt_names:
            img = Image.open(io.BytesIO(gt.read(gt_names[pid]))).convert("RGB")
            img.thumbnail((1600, 1600))
            img.save(OUT / "clear" / f"{pid}.jpg", quality=92)
            rows.append(dict(set="clear", file=f"clear/{pid}.jpg", id=pid, truth=truth,
                             unreadable=unreadable, reader_a=""))

    # Indian plates: one photo per original file, fixed random sample.
    reads = {r["id"]: r for r in csv.DictReader(open(ROOT / "experiments/results/reader_a_zenitsu_reads.csv"))}
    t = pq.read_table(RAW / "zenitsu09_indian_number_plate" / "train.parquet").to_pylist()
    seen, unique = set(), []
    for r in t:
        if r["orig_filename"] in seen:
            continue
        seen.add(r["orig_filename"])
        unique.append(r)
    random.Random(args.seed).shuffle(unique)
    for n, r in enumerate(unique[: args.indian]):
        Image.open(io.BytesIO(r["image"]["bytes"])).convert("RGB").save(OUT / "indian" / f"{n}.png")
        ra = reads.get(r["orig_filename"], {})
        rows.append(dict(set="indian", file=f"indian/{n}.png", id=r["orig_filename"],
                         truth=r["plate_text"].upper().replace(" ", ""), unreadable=False,
                         reader_a=ra.get("read", "")))

    with open(OUT / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    counts = {s: sum(r["set"] == s for r in rows) for s in ("foggy", "clear", "indian")}
    print("bundle:", OUT, counts)


if __name__ == "__main__":
    main()
