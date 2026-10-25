"""Run the whole simulated benchmark and print the results table.

    python -m tula.evaluate --passages 120000 --alpha 0.005

Half the passages calibrate the cut-offs, half are the test. Groups are
(plate style, time of day, weather). "Wrong" means the bill goes to the wrong
account or for the wrong amount. Readers are simulated (tula.readers_sim)
until real readers replace them, so these numbers test the method, not a
real toll operator.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from tula import readers_sim as rs
from tula.crc import CHARGE, HOLD, REVIEW, GroupController, min_group_size
from tula.evidence import LearnedScore, check
from tula.simulate import COLOURS, MAKES, make_passages, make_registry

ROOT = Path(__file__).resolve().parents[2]
VTYPES = sorted(MAKES)


def build_cases(n_vehicles: int, n_passages: int, seed: int, rates: dict | None = None,
                vehicles: list | None = None) -> list[dict]:
    rng = random.Random(seed)
    vehicles = vehicles or make_registry(n_vehicles, rng)
    passages = make_passages(vehicles, n_passages, rng, rates)
    by_id = {v.vehicle_id: v for v in vehicles}
    by_tag = {v.tag_id: v for v in vehicles}
    by_plate = {v.plate: v for v in vehicles}
    rng_a, rng_b, rng_split = random.Random(seed + 1), random.Random(seed + 2), random.Random(seed + 3)
    colours = list(COLOURS)

    cases = []
    for p in passages:
        car = by_id[p.true_vehicle_id]
        args = (p.shown_plate, car, p.time_of_day, p.weather)
        a = rs.read(rs.READER_A, *args, rng_a, colours, MAKES, VTYPES)
        b = rs.read(rs.READER_B, *args, rng_b, colours, MAKES, VTYPES)
        case = {"p": p, "group": (car.plate_style, p.time_of_day, p.weather),
                "split": rng_split.choices(["fit", "cal", "test"], [0.2, 0.4, 0.4])[0]}
        for name, use_a, use_b in (("fused", True, True), ("ocr", True, False), ("vlm", False, True)):
            ev = check(a, b, p.tag_read, p.tag_class, by_tag, by_plate, use_a, use_b)
            wrong = ev.target is not None and (ev.target != p.correct_account or ev.fee != p.correct_fee)
            case[name] = (ev.score, wrong, ev.target is not None)
            case[name + "_signals"] = ev.signals
        case["ocr_conf"] = 1 - a["plate_confidence"]  # today's single-threshold signal
        cases.append(case)
    return cases


def summarise(name: str, decisions: list[str], cases: list[dict], wrong_key, alpha: float) -> dict:
    n = len(cases)
    per_group = defaultdict(lambda: [0, 0])
    charged = wrong = holds = reviews = 0
    for d, c in zip(decisions, cases):
        per_group[c["group"]][0] += 1
        if d == CHARGE:
            charged += 1
            if wrong_key(c):
                wrong += 1
                per_group[c["group"]][1] += 1
        holds += d == HOLD
        reviews += d == REVIEW
    rates = {g: w / m for g, (m, w) in per_group.items() if m}
    worst = max(rates, key=rates.get)
    return {
        "method": name, "wrong_charge_rate": wrong / n, "automation_rate": charged / n,
        "hold_rate": holds / n, "review_rate": reviews / n, "wrong_charges": wrong,
        "worst_group": "/".join(worst), "worst_group_rate": rates[worst],
        "groups_over_alpha": sum(r > alpha for r in rates.values()), "groups": len(rates),
    }


def run(n_vehicles: int, n_passages: int, seed: int, alpha: float, delta: float = 0.1) -> dict:
    cases = build_cases(n_vehicles, n_passages, seed)
    fit = [c for c in cases if c["split"] == "fit"]
    cal = [c for c in cases if c["split"] == "cal"]
    test = [c for c in cases if c["split"] == "test"]
    results = []

    # Today's practice: trust the tag, else the plate; no doubt, no review.
    dec = [CHARGE if c["p"].naive_account else REVIEW for c in test]
    results.append(summarise("naive biller (today)", dec, test, lambda c: c["p"].naive_wrong_charge, alpha))

    # Today's practice: one OCR-confidence threshold (0.9) for all traffic, tag first.
    dec = [CHARGE if c["ocr"][2] and c["ocr_conf"] <= 0.1 else REVIEW for c in test]
    results.append(summarise("single threshold (0.9)", dec, test, lambda c: c["ocr"][1], alpha))

    # Fused score with a fixed cut-off, no risk controller.
    dec = [CHARGE if c["fused"][0] <= 0.3 else REVIEW for c in test]
    results.append(summarise("fused, fixed cut-off", dec, test, lambda c: c["fused"][1], alpha))

    # Learned score: weights fit on the fit split only, then calibrated as usual.
    for key in ("ocr", "vlm", "fused"):
        model = LearnedScore().fit([c[key + "_signals"] for c in fit], [c[key][1] for c in fit])
        for c in cal + test:
            c[key + "_learned"] = (model.score(c[key + "_signals"], c[key][2]), c[key][1], c[key][2])

    controllers = {}
    for key, label, d in (("ocr_learned", "OCR only + controller", None),
                          ("vlm_learned", "Muse only + controller", None),
                          ("fused", "TULA, hand-set score", None),
                          ("fused_learned", "TULA (fused + controller)", None),
                          ("fused_learned", f"TULA, {1 - delta:.0%} confidence", delta)):
        ctl = GroupController(alpha, delta=d).fit([c["group"] for c in cal], [c[key][0] for c in cal],
                                         [c[key][1] for c in cal])
        controllers[label] = ctl
        dec = [ctl.decide(c["group"], c[key][0]) for c in test]
        results.append(summarise(label, dec, test, lambda c, k=key: c[k][1], alpha))

    ctl = controllers["TULA (fused + controller)"]
    groups = sorted(ctl.sizes)
    return {
        "seed": seed, "alpha": alpha, "delta": delta, "passages": n_passages, "vehicles": n_vehicles,
        "fit": len(fit), "calibration": len(cal), "test": len(test), "min_group_size_to_certify": min_group_size(alpha),
        "certified_groups": sum(ctl.certified(g) for g in groups), "groups": len(groups),
        "uncertified": ["/".join(g) for g in groups if not ctl.certified(g)],
        "results": results,
    }


def table(report: dict) -> str:
    head = "| Method | Wrong-charge rate | Automated | Held | To human | Worst group (rate) | Groups over α |"
    rows = [head, "|" + "---|" * 7]
    for r in report["results"]:
        rows.append(f"| {r['method']} | {r['wrong_charge_rate']:.4%} | {r['automation_rate']:.1%} | "
                    f"{r['hold_rate']:.1%} | {r['review_rate']:.1%} | {r['worst_group']} "
                    f"({r['worst_group_rate']:.3%}) | {r['groups_over_alpha']}/{r['groups']} |")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the simulated TULA benchmark.")
    ap.add_argument("--vehicles", type=int, default=20000)
    ap.add_argument("--passages", type=int, default=120000)
    ap.add_argument("--alpha", type=float, default=0.005)
    ap.add_argument("--delta", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=26)
    ap.add_argument("--out", default=str(ROOT / "experiments" / "results"))
    args = ap.parse_args(argv)

    report = run(args.vehicles, args.passages, args.seed, args.alpha, args.delta)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"sim_seed{args.seed}_alpha{args.alpha}"
    (out / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n")
    md = (f"Target α = {args.alpha} wrong charges per passage, per group. "
          f"{report['certified_groups']}/{report['groups']} groups certified "
          f"(a group needs ≥ {report['min_group_size_to_certify']} calibration passages).\n\n" + table(report))
    (out / f"{stem}.md").write_text(md + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
