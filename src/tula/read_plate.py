"""Command line: read one plate image with Muse Spark and save a receipt.

    python -m tula.read_plate data/samples/synthetic_plate.png
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from tula.muse import ReaderError, read_plate

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read a number plate with Muse Spark.")
    p.add_argument("image", help="path to a plate or vehicle image")
    p.add_argument("--model", help="override the model id (default muse-spark-1.1)")
    p.add_argument("--out", default=str(ROOT / "experiments" / "receipts"),
                   help="folder for the JSON receipt")
    args = p.parse_args(argv)

    try:
        result = read_plate(args.image, model=args.model)
    except ReaderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt = {"image": str(args.image), "time_utc": stamp, **result}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"muse_read_{stamp}.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")

    print(json.dumps(result["read"], indent=2))
    meta = result["meta"]
    print(f"\nmodel={meta['model']} mode={meta['format_mode']} latency={meta['latency_s']}s")
    if meta["schema_problems"]:
        print("schema problems: " + "; ".join(meta["schema_problems"]))
    print(f"receipt: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
