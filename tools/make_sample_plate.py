"""Draw a synthetic Indian-style plate for smoke tests (no real vehicle).

DL 00 ZZ 0000 uses series 00, which is not issued, so it identifies no one.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "data" / "samples" / "synthetic_plate.png"


def font(size):
    for name in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/Library/Fonts/Arial Bold.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


img = Image.new("RGB", (640, 220), (90, 90, 95))
d = ImageDraw.Draw(img)
d.rounded_rectangle([40, 50, 600, 170], radius=12, fill="white", outline="black", width=5)
d.rectangle([48, 58, 90, 162], fill=(20, 60, 160))
d.text((69, 140), "IND", fill="white", font=font(14), anchor="mm")
d.text((345, 110), "DL 00 ZZ 0000", fill="black", font=font(64), anchor="mm")
OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT)
print(OUT)
