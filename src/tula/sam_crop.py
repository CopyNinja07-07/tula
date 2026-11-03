"""Step 1 of the pipeline: SAM 3.1 finds the plate and the vehicle in a frame.

Runs Meta's SAM 3.1 on Apple Silicon through MLX (mlx-community/sam3.1-bf16,
converted from facebook/sam3.1). Text prompts pick what to find, so the same
model gives both the plate crop (for the readers) and the vehicle crop (for the
make, colour and type checks).

Run on one photo:
    PYTHONPATH=src .venv/bin/python -m tula.sam_crop path/to/photo.png
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

MODEL_ID = "mlx-community/sam3.1-bf16"


@dataclass
class Found:
    prompt: str
    score: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2


@lru_cache(maxsize=1)
def predictor(threshold: float = 0.3):
    from mlx_vlm.models.sam3.generate import Sam3Predictor
    from mlx_vlm.models.sam3_1.processing_sam3_1 import Sam31Processor
    from mlx_vlm.utils import get_model_path, load_model

    path = get_model_path(MODEL_ID)
    model = load_model(path)
    processor = Sam31Processor.from_pretrained(str(path))
    return Sam3Predictor(model, processor, score_threshold=threshold)


def find(image: Image.Image, prompt: str) -> list[Found]:
    result = predictor().predict(image, text_prompt=prompt)
    out = []
    for i in range(len(result.scores)):
        x1, y1, x2, y2 = (int(round(float(v))) for v in result.boxes[i])
        out.append(Found(prompt, float(result.scores[i]), (x1, y1, x2, y2)))
    return sorted(out, key=lambda f: f.score, reverse=True)


def crop(image: Image.Image, box, pad: float = 0.08) -> Image.Image:
    x1, y1, x2, y2 = box
    px, py = int((x2 - x1) * pad), int((y2 - y1) * pad)
    return image.crop((max(0, x1 - px), max(0, y1 - py),
                       min(image.width, x2 + px), min(image.height, y2 + py)))


def plate_and_vehicle(image: Image.Image) -> dict:
    """Best plate and best vehicle in the frame, or None for each if not found."""
    plates = find(image, "license plate")
    vehicles = find(image, "vehicle")
    return {"plate": plates[0] if plates else None,
            "vehicle": vehicles[0] if vehicles else None,
            "n_plates": len(plates), "n_vehicles": len(vehicles)}


if __name__ == "__main__":
    img = Image.open(sys.argv[1]).convert("RGB")
    t0 = time.time()
    res = plate_and_vehicle(img)
    print(f"{time.time() - t0:.1f}s", res)
    if res["plate"]:
        out = Path(sys.argv[1]).with_suffix(".plate.png").name
        crop(img, res["plate"].box).save(f"/tmp/{out}")
        print("plate crop saved to", f"/tmp/{out}")
