"""Offline tests for Reader B. A fake client stands in for the Meta Model API."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from tula.muse import parse_json, read_plate, validate

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "samples" / "synthetic_plate.png"

GOOD = {
    "plate_readable": True, "plate_text": "dl 00 zz 0000", "plate_confidence": 0.93,
    "plate_style": "single_line", "state_code": "dl", "vehicle_type": "car",
    "make": None, "colour": None, "image_issues": [],
}


class FakeClient:
    """Rejects the first `fail` calls (like an unsupported response_format), then answers."""

    def __init__(self, reply: str, fail: int = 0):
        self.reply, self.fail, self.calls = reply, fail, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self.fail:
            raise ValueError("response_format not supported")
        msg = SimpleNamespace(content=self.reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], model=kwargs["model"], usage=None)


class ReaderBTest(unittest.TestCase):
    def test_schema_mode_and_normalising(self):
        client = FakeClient(json.dumps(GOOD))
        out = read_plate(SAMPLE, client=client)
        self.assertEqual(out["read"]["plate_text"], "DL00ZZ0000")
        self.assertEqual(out["read"]["state_code"], "DL")
        self.assertEqual(out["meta"]["format_mode"], "json_schema")
        self.assertEqual(out["meta"]["schema_problems"], [])
        sent = client.calls[0]["messages"][1]["content"][1]["image_url"]["url"]
        self.assertTrue(sent.startswith("data:image/png;base64,"))

    def test_falls_back_when_schema_rejected(self):
        client = FakeClient("```json\n" + json.dumps(GOOD) + "\n```", fail=2)
        out = read_plate(SAMPLE, client=client)
        self.assertEqual(out["meta"]["format_mode"], "prompt_only")
        self.assertEqual(len(out["meta"]["earlier_errors"]), 2)
        self.assertNotIn("response_format", client.calls[-1])

    def test_validate_flags_bad_reads(self):
        bad = dict(GOOD, plate_text=None, plate_confidence=1.5, vehicle_type="spaceship")
        problems = validate(bad)
        self.assertEqual(len(problems), 3)

    def test_parse_json_with_chatter(self):
        self.assertEqual(parse_json('Sure! {"a": 1} hope that helps')["a"], 1)


if __name__ == "__main__":
    unittest.main()
