"""Reader A: a small specialist plate OCR model that sees the plate crop only.

Uses fast-plate-ocr (open source, ONNX, runs on the Mac CPU). It never sees
Reader B's answer or the registry (whitepaper Section 3.1).

    python -m tula.reader_a                # measure on the labelled Indian plates
"""
from __future__ import annotations

import argparse
import io
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from tula.evidence import edit_distance

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "cct-s-v2-global-model"
LABELLED = ROOT / "data" / "raw" / "zenitsu09_indian_number_plate" / "train.parquet"


class ReaderA:
    def __init__(self, model: str = DEFAULT_MODEL):
        from fast_plate_ocr import LicensePlateRecognizer
        self.model_name = model
        self.model = LicensePlateRecognizer(model, device="cpu")

    def read(self, image: Image.Image) -> dict:
        pred = self.model.run(np.array(image.convert("RGB")), return_confidence=True)[0]
        text = re.sub(r"[^A-Z0-9]", "", pred.plate.upper())
        probs = [float(p) for p in pred.char_probs]
        # Confidence of the whole plate = its weakest character.
        return {"plate_text": text or None, "plate_confidence": round(min(probs), 4) if probs else 0.0}


def load_labelled(path: Path = LABELLED) -> list[dict]:
    """Unique labelled photos, cropped to the plate box when the photo is a full frame."""
    import pyarrow.parquet as pq
    t = pq.read_table(path).to_pydict()
    seen, rows = set(), []
    for i, name in enumerate(t["orig_filename"]):
        base = re.sub(r"\.rf\.[0-9a-f]+", "", name)  # Roboflow augmented copies share a base name
        if base in seen:
            continue
        seen.add(base)
        img = Image.open(io.BytesIO(t["image"][i]["bytes"]))
        box = [t[k][i] for k in ("xmin", "ymin", "xmax", "ymax")]
        if all(box):
            x0, y0, x1, y1 = (int(float(v)) for v in box)
            # Most photos are already crops and the box refers to the original frame.
            if x1 <= img.size[0] and y1 <= img.size[1] and (x1 - x0, y1 - y0) != img.size:
                img = img.crop((x0, y0, x1, y1))
        rows.append({"id": base, "image": img, "truth": re.sub(r"[^A-Z0-9]", "", t["plate_text"][i].upper())})
    return rows


def size_bucket(img: Image.Image) -> str:
    w = img.size[0]
    return "tiny (<100px)" if w < 100 else "small (100-200px)" if w < 200 else "large (200px+)"


def measure(model: str = DEFAULT_MODEL, out_dir: Path = ROOT / "experiments" / "results") -> dict:
    reader, rows = ReaderA(model), load_labelled()
    per_image, buckets = [], defaultdict(lambda: [0, 0, 0.0])
    for r in rows:
        got = reader.read(r["image"])
        text = got["plate_text"] or ""
        cer = edit_distance(text, r["truth"]) / max(1, len(r["truth"]))
        ok = text == r["truth"]
        b = size_bucket(r["image"])
        buckets[b][0] += 1
        buckets[b][1] += ok
        buckets[b][2] += cer
        per_image.append({"id": r["id"], "truth": r["truth"], "read": text,
                          "confidence": got["plate_confidence"], "exact": ok, "cer": round(cer, 4), "size": b})

    n = len(per_image)
    exact = sum(p["exact"] for p in per_image)
    # Is confidence honest? Accuracy among reads the model was >= 0.9 sure about.
    sure = [p for p in per_image if p["confidence"] >= 0.9]
    report = {
        "model": model, "images": n, "exact_match": exact / n,
        "char_error_rate": sum(p["cer"] for p in per_image) / n,
        "confident_reads": len(sure), "confident_but_wrong": sum(not p["exact"] for p in sure),
        "by_size": {b: {"images": m, "exact_match": k / m, "char_error_rate": c / m}
                    for b, (m, k, c) in sorted(buckets.items())},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reader_a_zenitsu.json").write_text(json.dumps(report, indent=2) + "\n")
    with (out_dir / "reader_a_zenitsu_reads.csv").open("w") as f:
        f.write("id,truth,read,confidence,exact,cer,size\n")
        for p in per_image:
            f.write(",".join(str(p[k]) for k in ("id", "truth", "read", "confidence", "exact", "cer", "size")) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure Reader A on labelled Indian plates.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args(argv)
    print(json.dumps(measure(args.model), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
