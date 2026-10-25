"""Simulated readers, used until real readers run on real photos.

Each reader makes character mistakes at a rate that depends on plate style,
time of day and weather, and reports a confidence that is only loosely tied
to whether it was right (real models are overconfident). Reader A and Reader B
draw from separate random streams, so their mistakes are independent, which is
the design goal of input isolation (whitepaper Section 3.1). These rates are
assumptions: once Reader A runs on real photos, its measured rates replace them.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

ALPHANUM = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
LOOKALIKE = {"0": "OD", "O": "0D", "D": "0O", "1": "I7", "I": "1", "8": "B", "B": "8", "5": "S", "S": "5",
             "2": "Z", "Z": "2", "6": "G", "G": "6", "M": "N", "N": "M", "H": "N", "U": "V", "V": "U"}

TIME_X = {"day": 1.0, "night": 2.5}
WEATHER_X = {"clear": 1.0, "rain": 1.8, "fog": 3.0}


@dataclass
class ReaderProfile:
    name: str
    char_error: dict          # plate_style -> per-character error probability in day/clear
    attr_error: float = 0.0   # chance of misreading colour / make (Reader B only)
    type_error: float = 0.0
    reads_attributes: bool = False


# Reader A: specialist OCR, strong on clean printed plates, weak on odd fonts.
READER_A = ReaderProfile("ocr", {"high_security": 0.004, "single_line": 0.007, "two_line": 0.035, "hand_painted": 0.06})
# Reader B: VLM, a bit worse on clean plates, better on odd layouts, also reads the vehicle.
READER_B = ReaderProfile("vlm", {"high_security": 0.008, "single_line": 0.01, "two_line": 0.015, "hand_painted": 0.03},
                         attr_error=0.08, type_error=0.03, reads_attributes=True)


def _corrupt(ch: str, rng: random.Random) -> str:
    if ch in LOOKALIKE and rng.random() < 0.7:
        return rng.choice(LOOKALIKE[ch])
    return rng.choice([c for c in ALPHANUM if c != ch])


def read(profile: ReaderProfile, plate: str, vehicle, time_of_day: str, weather: str,
         rng: random.Random, colours: list[str], makes: dict, vehicle_types: list[str]) -> dict:
    p = min(0.5, profile.char_error[vehicle.plate_style] * TIME_X[time_of_day] * WEATHER_X[weather])
    chars = [(_corrupt(c, rng) if rng.random() < p else c) for c in plate]
    if rng.random() < p / 2:  # dropped character
        del chars[rng.randrange(len(chars))]
    text = "".join(chars)
    n_wrong = sum(a != b for a, b in zip(text, plate)) + abs(len(text) - len(plate))
    conf = max(0.0, min(1.0, rng.gauss(0.97 - 0.12 * n_wrong - 2 * p, 0.05)))
    out = {"plate_text": text if n_wrong < 5 else None, "plate_confidence": round(conf, 3)}
    if profile.reads_attributes:
        night = 2.0 if time_of_day == "night" else 1.0
        out["vehicle_type"] = (rng.choice(vehicle_types) if rng.random() < profile.type_error * night
                               else vehicle.vehicle_type)
        out["colour"] = rng.choice(colours) if rng.random() < profile.attr_error * night else vehicle.colour
        out["make"] = (rng.choice(makes[vehicle.vehicle_type]) if rng.random() < profile.attr_error * night
                       else vehicle.make)
    return out
