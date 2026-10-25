"""The recursive loop: can a billing AI safely learn from its own past decisions?

After deployment, the only feedback is disputes. But only charged people can
dispute, and many wrongly charged people never do (a cloned-plate victim may
not notice). So "no dispute" is not "correct". A system that recalibrates on
dispute labels teaches itself that its mistakes were fine, loosens its cut-off,
charges more, and the loop repeats. Attackers make it worse: when cloned plates
get through, more people clone.

Two systems run side by side for several rounds on the same traffic:
  naive  recalibrates on everything it has labels for: disputes on charged
         passages ("no dispute" = correct) plus human reviews.
  TULA   recalibrates only on a small uniform random audit of all traffic,
         which is exchangeable with future traffic, so the bound still holds.
Each round we also record what each system believes its wrong-charge rate is,
next to the true rate.

    python -m tula.feedback
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from tula.crc import CHARGE, REVIEW, GroupController
from tula.evaluate import build_cases
from tula.simulate import DEFAULT_SCENARIO_RATES, make_registry

ROOT = Path(__file__).resolve().parents[2]
DISPUTE_P = {"tag_swap": 0.6, "wrong_class": 0.7, "cloned_plate": 0.3}  # chance a wrong charge is disputed
CLONE_GROWTH = 4.0  # how fast cloning spreads when clones get charged to victims


def run(rounds: int, per_round: int, alpha: float, audit_rate: float, seed: int, key: str = "fused") -> dict:
    rng = random.Random(seed)
    vehicles = make_registry(20000, random.Random(seed))
    rates = dict(DEFAULT_SCENARIO_RATES)
    pilot = build_cases(0, per_round, seed, rates, vehicles)
    # Round 0: both systems start from the same small, fully labelled pilot.
    start = rng.sample(pilot, int(0.25 * len(pilot)))
    labelled = {"naive": [(c["group"], c[key][0], c[key][1]) for c in start],
                "tula": [(c["group"], c[key][0], c[key][1]) for c in start]}
    history = []
    for t in range(1, rounds + 1):
        cases = build_cases(0, per_round, seed + 100 * t, rates, vehicles)
        row = {"round": t, "clone_rate": rates["cloned_plate"]}
        clone_success = 0
        for name in ("naive", "tula"):
            data = labelled[name]
            ctl = GroupController(alpha, delta=0.1).fit([g for g, _, _ in data], [s for _, s, _ in data],
                                                        [w for _, _, w in data])
            dec = [ctl.decide(c["group"], c[key][0]) for c in cases]
            n = len(cases)
            wrong = [d == CHARGE and c[key][1] for d, c in zip(dec, cases)]
            disputed = [w and rng.random() < DISPUTE_P.get(c["p"].scenario, 0.5) for w, c in zip(wrong, cases)]
            if name == "naive":
                # Labels it gets for free: charged -> wrong only if disputed; reviewed -> true label.
                for d, c, disp in zip(dec, cases, disputed):
                    if d == CHARGE:
                        data.append((c["group"], c[key][0], disp))
                    elif d == REVIEW:
                        data.append((c["group"], c[key][0], c[key][1]))
                believed = sum(disputed) / n
            else:
                audit = [c for c in cases if rng.random() < audit_rate]
                data.extend((c["group"], c[key][0], c[key][1]) for c in audit)
                audited_wrong = sum(1 for c in audit if ctl.decide(c["group"], c[key][0]) == CHARGE and c[key][1])
                believed = audited_wrong / max(1, len(audit))
            row[name] = {"true_wrong_rate": sum(wrong) / n, "believed_wrong_rate": believed,
                         "automation_rate": dec.count(CHARGE) / n}
            if name == "naive":
                clone_success = sum(1 for w, c in zip(wrong, cases) if w and c["p"].scenario == "cloned_plate")
        history.append(row)
        # Attackers adapt to the naive system's leaks: cloning grows with its success.
        clones = sum(1 for c in cases if c["p"].scenario == "cloned_plate") or 1
        rates["cloned_plate"] = min(0.15, rates["cloned_plate"] * (1 + CLONE_GROWTH * clone_success / clones))
        rates["clean"] = 1 - sum(v for k, v in rates.items() if k != "clean")
    return {"alpha": alpha, "audit_rate": audit_rate, "rounds": rounds, "per_round": per_round, "history": history}


def table(report: dict) -> str:
    lines = [f"Promise α = {report['alpha']:.1%}. TULA audits {report['audit_rate']:.0%} of traffic at random.", "",
             "| Round | Clone rate | Naive: true wrong | Naive: believes | Naive: automated | "
             "TULA: true wrong | TULA: believes | TULA: automated |", "|---|---|---|---|---|---|---|---|"]
    for r in report["history"]:
        nv, tl = r["naive"], r["tula"]
        lines.append(f"| {r['round']} | {r['clone_rate']:.1%} | {nv['true_wrong_rate']:.2%} | {nv['believed_wrong_rate']:.2%} | "
                     f"{nv['automation_rate']:.1%} | {tl['true_wrong_rate']:.2%} | {tl['believed_wrong_rate']:.2%} | "
                     f"{tl['automation_rate']:.1%} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Learning from disputes: naive vs TULA over rounds.")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--per-round", type=int, default=30000)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--audit-rate", type=float, default=0.03)
    ap.add_argument("--seed", type=int, default=26)
    args = ap.parse_args(argv)
    report = run(args.rounds, args.per_round, args.alpha, args.audit_rate, args.seed)
    md = table(report)
    out = ROOT / "experiments" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"feedback_seed{args.seed}.md").write_text(md + "\n")
    (out / f"feedback_seed{args.seed}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
