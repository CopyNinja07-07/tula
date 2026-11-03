"""Reader A on the SAM 3.1 plate crops of the foggy and clear photos.

Output: experiments/results/reader_a_sam31_reads.csv (set, file, truth, read, confidence).
Run: PYTHONPATH=src .venv/bin/python tools/reader_a_on_sam.py
"""
from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image

from tula.reader_a import ReaderA

ROOT = Path(__file__).resolve().parents[1]
CROPS = ROOT / "data" / "raw" / "sam_crops" / "plate"
OUT = ROOT / "experiments" / "results" / "reader_a_sam31_reads.csv"


def main() -> None:
    reader = ReaderA()
    rows = list(csv.DictReader(open(ROOT / "experiments" / "results" / "sam31_boxes.csv")))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["set", "file", "truth", "read", "confidence"])
        w.writeheader()
        for r in rows:
            crop = CROPS / (r["file"].replace("/", "_").rsplit(".", 1)[0] + ".png")
            read = reader.read(Image.open(crop)) if crop.exists() else {"plate_text": None, "plate_confidence": 0.0}
            w.writerow(dict(set=r["set"], file=r["file"], truth=r["truth"],
                            read=read["plate_text"] or "", confidence=read["plate_confidence"]))
    print("saved", OUT)


if __name__ == "__main__":
    main()
