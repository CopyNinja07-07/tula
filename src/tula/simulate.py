"""Simulated FASTag, registry and billing layers for the TULA benchmark.

Everything here is made up: random plates, no owner names, no real accounts.
The point is to know the ground truth for every toll passage, so we can
count exactly how often a billing rule charges the wrong person.

Each passage has a scenario:
  clean         right tag on the right car
  tag_missing   tag not read (dead tag, bad mount); billing falls back to the plate
  tag_swap      the car carries another vehicle's tag
  cloned_plate  the car shows another registered vehicle's plate
  wrong_class   the tag is registered with the wrong toll class

    python -m tula.simulate --vehicles 5000 --passages 20000
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STATES = ["DL", "HR", "UP", "RJ", "MH", "GJ", "KA", "TN", "KL", "TS", "AP", "WB", "PB", "MP", "BR"]
PLATE_STYLES = {"high_security": 0.62, "single_line": 0.22, "two_line": 0.10, "hand_painted": 0.06}
COLOURS = {"white": 0.38, "silver": 0.18, "grey": 0.14, "black": 0.10, "red": 0.08, "blue": 0.07, "other": 0.05}

# Toll classes follow NHAI's fee categories. Fees are illustrative, not a real plaza's rates.
TOLL_CLASSES = {
    "car_jeep_van": {"vehicle_types": {"car": 0.62, "suv": 0.30, "van": 0.08}, "fee": 120, "share": 0.78},
    "lcv":          {"vehicle_types": {"van": 0.4, "truck": 0.6}, "fee": 195, "share": 0.08},
    "bus_truck":    {"vehicle_types": {"bus": 0.35, "truck": 0.65}, "fee": 410, "share": 0.09},
    "multi_axle":   {"vehicle_types": {"truck": 1.0}, "fee": 630, "share": 0.05},
}
MAKES = {
    "car": ["Maruti Suzuki", "Hyundai", "Tata", "Honda", "Toyota", "Kia"],
    "suv": ["Mahindra", "Tata", "Hyundai", "Kia", "Toyota", "MG"],
    "van": ["Maruti Suzuki", "Force", "Tata"],
    "bus": ["Ashok Leyland", "Tata", "Eicher"],
    "truck": ["Tata", "Ashok Leyland", "Eicher", "BharatBenz", "Mahindra"],
}

# Base rates are guesses in the range the brief's sources suggest (faulty
# FASTag deductions ~0.03%, MLFF misreads, clone reports). The benchmark
# over-samples rare scenarios and the calibration step re-weights them.
DEFAULT_SCENARIO_RATES = {
    "clean": 0.90, "tag_missing": 0.04, "tag_swap": 0.025, "cloned_plate": 0.02, "wrong_class": 0.015,
}
TIME_OF_DAY = {"day": 0.68, "night": 0.32}
WEATHER = {"clear": 0.78, "rain": 0.14, "fog": 0.08}


@dataclass
class Vehicle:
    vehicle_id: str
    plate: str
    state: str
    plate_style: str
    toll_class: str
    vehicle_type: str
    make: str
    colour: str
    tag_id: str
    tag_class: str  # class the tag is registered under; usually equals toll_class


@dataclass
class Passage:
    passage_id: str
    plaza: str
    time_of_day: str
    weather: str
    scenario: str
    true_vehicle_id: str       # the car physically passing
    shown_plate: str           # plate on the car (differs from its own when cloned)
    tag_read: str | None       # tag id the reader picked up, None if not read
    correct_account: str       # vehicle_id that should pay
    correct_fee: int
    naive_account: str | None  # who a tag-first, plate-fallback biller charges
    naive_fee: int | None
    naive_wrong_charge: bool   # charged someone else or the wrong amount
    image_ref: str | None = None  # filled when a real plate image is attached


def pick(rng: random.Random, weights: dict) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def make_plate(rng: random.Random, state: str, taken: set[str]) -> str:
    while True:
        plate = (f"{state}{rng.randint(1, 99):02d}"
                 f"{rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}{rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}"
                 f"{rng.randint(1, 9999):04d}")
        if plate not in taken:
            taken.add(plate)
            return plate


def make_registry(n: int, rng: random.Random) -> list[Vehicle]:
    taken: set[str] = set()
    shares = {k: v["share"] for k, v in TOLL_CLASSES.items()}
    out = []
    for i in range(n):
        state = rng.choice(STATES)
        toll_class = pick(rng, shares)
        vtype = pick(rng, TOLL_CLASSES[toll_class]["vehicle_types"])
        out.append(Vehicle(
            vehicle_id=f"V{i:06d}", plate=make_plate(rng, state, taken), state=state,
            plate_style=pick(rng, PLATE_STYLES), toll_class=toll_class, vehicle_type=vtype,
            make=rng.choice(MAKES[vtype]), colour=pick(rng, COLOURS),
            tag_id=f"TAG{rng.getrandbits(40):012X}", tag_class=toll_class,
        ))
    return out


def _wrong_class(rng: random.Random, toll_class: str) -> str:
    return rng.choice([c for c in TOLL_CLASSES if c != toll_class])


def make_passages(vehicles: list[Vehicle], n: int, rng: random.Random,
                  rates: dict[str, float] | None = None, plazas: int = 4) -> list[Passage]:
    rates = rates or DEFAULT_SCENARIO_RATES
    by_tag = {v.tag_id: v for v in vehicles}
    by_plate = {v.plate: v for v in vehicles}
    out = []
    for i in range(n):
        car = rng.choice(vehicles)
        scenario = pick(rng, rates)
        other = rng.choice([v for v in rng.sample(vehicles, 3) if v is not car] or vehicles)
        shown_plate, tag_read, tag_class = car.plate, car.tag_id, car.tag_class
        if scenario == "tag_missing":
            tag_read = None
        elif scenario == "tag_swap":
            tag_read = other.tag_id
        elif scenario == "cloned_plate":
            shown_plate, tag_read = other.plate, None  # cloners usually carry no tag
        elif scenario == "wrong_class":
            tag_class = _wrong_class(rng, car.toll_class)

        correct_fee = TOLL_CLASSES[car.toll_class]["fee"]
        # Naive biller: trust the tag; if no tag, trust the plate read (assumed perfect here,
        # so every naive error below comes from the evidence, not from OCR).
        if tag_read is not None:
            naive = by_tag[tag_read]
            naive_account = naive.vehicle_id
            naive_fee = TOLL_CLASSES[tag_class if naive is car else naive.tag_class]["fee"]
        else:
            naive = by_plate.get(shown_plate)
            naive_account = naive.vehicle_id if naive else None
            naive_fee = TOLL_CLASSES[naive.toll_class]["fee"] if naive else None
        wrong = naive_account is not None and (naive_account != car.vehicle_id or naive_fee != correct_fee)

        out.append(Passage(
            passage_id=f"P{i:07d}", plaza=f"PLAZA{rng.randrange(plazas) + 1}",
            time_of_day=pick(rng, TIME_OF_DAY), weather=pick(rng, WEATHER), scenario=scenario,
            true_vehicle_id=car.vehicle_id, shown_plate=shown_plate, tag_read=tag_read,
            correct_account=car.vehicle_id, correct_fee=correct_fee,
            naive_account=naive_account, naive_fee=naive_fee, naive_wrong_charge=wrong,
        ))
    return out


def write_csv(rows: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dicts = [asdict(r) for r in rows]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dicts[0]))
        w.writeheader()
        w.writerows(dicts)


def summarise(passages: list[Passage]) -> dict:
    total = len(passages)
    by_scenario: dict[str, dict[str, int]] = {}
    for p in passages:
        s = by_scenario.setdefault(p.scenario, {"passages": 0, "naive_wrong": 0})
        s["passages"] += 1
        s["naive_wrong"] += p.naive_wrong_charge
    wrong = sum(p.naive_wrong_charge for p in passages)
    return {"passages": total, "naive_wrong_charges": wrong,
            "naive_wrong_rate": round(wrong / total, 5) if total else 0.0, "by_scenario": by_scenario}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build the simulated tag, registry and billing layers.")
    p.add_argument("--vehicles", type=int, default=5000)
    p.add_argument("--passages", type=int, default=20000)
    p.add_argument("--seed", type=int, default=26)
    p.add_argument("--out", default=str(ROOT / "data" / "synthetic"))
    args = p.parse_args(argv)

    rng = random.Random(args.seed)
    vehicles = make_registry(args.vehicles, rng)
    passages = make_passages(vehicles, args.passages, rng)
    out = Path(args.out)
    write_csv(vehicles, out / "registry.csv")
    write_csv(passages, out / "passages.csv")
    summary = {"seed": args.seed, "vehicles": len(vehicles), **summarise(passages)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
