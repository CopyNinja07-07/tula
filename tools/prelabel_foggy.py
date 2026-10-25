"""Find the plate in each foggy photo, pre-read it, and build a checking page.

The pre-reads are only a starting point. A person confirms or corrects every
plate in label_foggy.html, because readers can't be graded on their own answers.

    PYTHONPATH=src .venv/bin/python tools/prelabel_foggy.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FOGGY = ROOT / "data" / "raw" / "foggy_hazy_plates_mendeley"
PHOTOS = FOGGY / "New Hazy dataset"
CROPS = FOGGY / "crops"
DETECTOR = "yolo-v9-t-640-license-plate-end2end"


def main() -> int:
    from open_image_models import LicensePlateDetector
    from tula.reader_a import ReaderA

    detector, reader = LicensePlateDetector(detection_model=DETECTOR), ReaderA()
    CROPS.mkdir(exist_ok=True)
    photos = sorted(PHOTOS.glob("*.png"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
    rows = []
    for i, path in enumerate(photos, 1):
        img = Image.open(path).convert("RGB")
        found = detector.predict(np.array(img)[:, :, ::-1])  # detector expects BGR
        row = {"id": path.stem, "photo": f"New Hazy dataset/{path.name}", "plates_found": len(found),
               "det_conf": "", "crop": "", "pre_read": "", "pre_conf": ""}
        if found:
            best = max(found, key=lambda d: d.confidence)
            b = best.bounding_box
            pad_x, pad_y = int(0.08 * (b.x2 - b.x1)), int(0.15 * (b.y2 - b.y1))
            crop = img.crop((max(0, b.x1 - pad_x), max(0, b.y1 - pad_y),
                             min(img.width, b.x2 + pad_x), min(img.height, b.y2 + pad_y)))
            crop.save(CROPS / f"{path.stem}.png")
            read = reader.read(crop)
            row.update(det_conf=round(best.confidence, 3), crop=f"crops/{path.stem}.png",
                       pre_read=read["plate_text"] or "", pre_conf=read["plate_confidence"])
        rows.append(row)
        if i % 100 == 0:
            print(f"{i}/{len(photos)}", file=sys.stderr)

    with (FOGGY / "prelabels.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    page = (ROOT / "tools" / "label_page.html").read_text()
    (FOGGY / "label_foggy.html").write_text(page.replace("/*ROWS*/[]", json.dumps(rows).replace("</", "<\\/")))
    found = sum(r["plates_found"] > 0 for r in rows)
    print(json.dumps({"photos": len(rows), "plate_found": found, "no_plate_found": len(rows) - found}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
