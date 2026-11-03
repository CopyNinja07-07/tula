"""Run SAM 3.1 over the photo bundle: find plate + vehicle, save crops and boxes.

Output: experiments/results/sam31_boxes.csv and crops in data/raw/sam_crops/.
Run: PYTHONPATH=src .venv/bin/python tools/run_sam_bundle.py [--sets foggy,clear]
"""
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from PIL import Image

from tula.sam_crop import crop, plate_and_vehicle

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "raw" / "kaggle_bundle"
CROPS = ROOT / "data" / "raw" / "sam_crops"
OUT = ROOT / "experiments" / "results" / "sam31_boxes.csv"
FIELDS = ["set", "file", "truth", "plate_score", "plate_box", "vehicle_score", "vehicle_box",
          "n_plates", "n_vehicles", "seconds"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="foggy,clear")
    sets = ap.parse_args().sets.split(",")
    rows = [r for r in csv.DictReader(open(BUNDLE / "manifest.csv")) if r["set"] in sets]
    done = set()
    if OUT.exists():
        done = {r["file"] for r in csv.DictReader(open(OUT))}
    new = not OUT.exists()
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, r in enumerate(rows, 1):
            if r["file"] in done:
                continue
            img = Image.open(BUNDLE / r["file"]).convert("RGB")
            t0 = time.time()
            res = plate_and_vehicle(img)
            sec = round(time.time() - t0, 2)
            p, v = res["plate"], res["vehicle"]
            stem = r["file"].replace("/", "_").rsplit(".", 1)[0]
            if p:
                (CROPS / "plate").mkdir(parents=True, exist_ok=True)
                crop(img, p.box).save(CROPS / "plate" / f"{stem}.png")
            if v:
                (CROPS / "vehicle").mkdir(parents=True, exist_ok=True)
                crop(img, v.box, pad=0.02).save(CROPS / "vehicle" / f"{stem}.jpg", quality=90)
            w.writerow(dict(set=r["set"], file=r["file"], truth=r["truth"],
                            plate_score=round(p.score, 3) if p else "", plate_box=p.box if p else "",
                            vehicle_score=round(v.score, 3) if v else "", vehicle_box=v.box if v else "",
                            n_plates=res["n_plates"], n_vehicles=res["n_vehicles"], seconds=sec))
            f.flush()
            if i % 25 == 0:
                print(f"{i}/{len(rows)}", flush=True)
    print("done", OUT)


if __name__ == "__main__":
    main()
