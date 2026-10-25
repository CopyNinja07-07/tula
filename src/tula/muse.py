"""Reader B: Muse Spark reads a plate image and returns structured JSON.

Muse Spark is reached through the Meta Model API, which speaks the OpenAI
Chat Completions format. The key comes from .env (META_API_KEY or
MODEL_API_KEY) and is never printed or written to a receipt.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "muse-spark-1.1"
DEFAULT_BASE = "https://api.meta.ai/v1"

PLATE_STYLES = ["single_line", "two_line", "hand_painted", "high_security", "other", "unknown"]
VEHICLE_TYPES = ["two_wheeler", "three_wheeler", "car", "suv", "van", "bus", "truck", "other", "unknown"]

PLATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "plate_readable", "plate_text", "plate_confidence", "plate_style",
        "state_code", "vehicle_type", "make", "colour", "image_issues",
    ],
    "properties": {
        "plate_readable": {"type": "boolean"},
        "plate_text": {"type": ["string", "null"]},
        "plate_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "plate_style": {"type": "string", "enum": PLATE_STYLES},
        "state_code": {"type": ["string", "null"]},
        "vehicle_type": {"type": "string", "enum": VEHICLE_TYPES},
        "make": {"type": ["string", "null"]},
        "colour": {"type": ["string", "null"]},
        "image_issues": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM_PROMPT = (
    "You are Reader B in a toll-billing safety system. You read Indian number "
    "plates from camera images. A wrong read can bill an innocent person, so "
    "never guess: if a character is not clearly visible, set plate_readable to "
    "false, plate_text to null and lower plate_confidence. Write plate_text in "
    "upper case with no spaces (e.g. KA01AB1234). state_code is the first two "
    "letters of the plate. Use null for anything you cannot see. List problems "
    "such as blur, glare, night, rain, fog, occlusion or tilt in image_issues. "
    "Reply with JSON only, matching the given schema."
)

USER_PROMPT = "Read this vehicle's number plate and describe the vehicle."


class ReaderError(RuntimeError):
    pass


def make_client():
    """Build an OpenAI-compatible client pointed at the Meta Model API."""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    key = os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")
    if not key:
        raise ReaderError("No API key found. Paste it into .env as META_API_KEY=...")
    base = os.environ.get("META_API_BASE") or DEFAULT_BASE
    return OpenAI(base_url=base, api_key=key)


def image_to_data_url(path: str | Path) -> str:
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _messages(data_url: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": USER_PROMPT},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]},
    ]


# Tried in order: strict schema first, then plain JSON mode, then prompt only.
# The docs confirm image input but not which response_format modes are live,
# so we fall back instead of failing on day one.
_FORMATS: list[tuple[str, dict[str, Any] | None]] = [
    ("json_schema", {"type": "json_schema",
                     "json_schema": {"name": "plate_read", "strict": True, "schema": PLATE_SCHEMA}}),
    ("json_object", {"type": "json_object"}),
    ("prompt_only", None),
]


def parse_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a reply, tolerating ```json fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ReaderError(f"Reply had no JSON object: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def validate(read: dict[str, Any]) -> list[str]:
    """Return a list of problems with a read; empty means it fits the schema."""
    problems = [f"missing {k}" for k in PLATE_SCHEMA["required"] if k not in read]
    conf = read.get("plate_confidence")
    if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        problems.append("plate_confidence must be a number from 0 to 1")
    if read.get("plate_style") not in PLATE_STYLES:
        problems.append(f"plate_style {read.get('plate_style')!r} not allowed")
    if read.get("vehicle_type") not in VEHICLE_TYPES:
        problems.append(f"vehicle_type {read.get('vehicle_type')!r} not allowed")
    if read.get("plate_readable") and not read.get("plate_text"):
        problems.append("plate_readable is true but plate_text is empty")
    return problems


def normalise(read: dict[str, Any]) -> dict[str, Any]:
    if read.get("plate_text"):
        read["plate_text"] = "".join(ch for ch in read["plate_text"].upper() if ch.isalnum())
    if read.get("state_code"):
        read["state_code"] = read["state_code"].upper()[:2]
    return read


def read_plate(image_path: str | Path, client=None, model: str | None = None) -> dict[str, Any]:
    """Send one image to Muse Spark and return {"read": ..., "meta": ...}."""
    client = client or make_client()
    model = model or os.environ.get("TULA_MUSE_MODEL") or DEFAULT_MODEL
    messages = _messages(image_to_data_url(image_path))

    errors = []
    for mode, response_format in _FORMATS:
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if response_format:
            kwargs["response_format"] = response_format
        started = time.perf_counter()
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:  # unsupported response_format -> try the next mode
            errors.append(f"{mode}: {type(exc).__name__}: {exc}"[:300])
            continue
        latency = time.perf_counter() - started
        text = resp.choices[0].message.content or ""
        read = normalise(parse_json(text))
        usage = getattr(resp, "usage", None)
        return {
            "read": read,
            "meta": {
                "model": getattr(resp, "model", model),
                "format_mode": mode,
                "latency_s": round(latency, 3),
                "usage": usage.model_dump() if hasattr(usage, "model_dump") else None,
                "schema_problems": validate(read),
                "earlier_errors": errors,
            },
        }
    raise ReaderError("All request formats failed:\n" + "\n".join(errors))
