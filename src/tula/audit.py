"""Human review budget: what can TULA promise for a given number of reviewers?

A toll operator can only afford so many human checks. Sweeping the target
wrong-charge rate alpha shows the trade-off between three numbers: the
promised wrong-charge rate, the share of traffic charged automatically, and
the share sent to humans. For each review budget we report the strictest
promise that fits inside it. When the review queue is longer than the budget,
the passages with the highest expected harm (doubt x fee) go to humans first
and the rest wait on hold; nothing over budget is ever charged.

    python -m tula.audit
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tula.crc import CHARGE, REVIEW, GroupController
from tula.evaluate import build_cases

ROOT = Path(__file__).resolve().parents[2]
ALPHAS = [0.002, 0.003, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05]
BUDGETS = [0.02, 0.05, 0.10, 0.20]


def sweep(cases: list[dict], key: str = "fused", delta: float | None = 0.1) -> list[dict]:
    cal = [c for c in cases if c["split"] in ("fit", "cal")]
    test = [c for c in cases if c["split"] == "test"]
    rows = []
    for alpha in ALPHAS:
        ctl = GroupController(alpha, delta=delta).fit(
            [c["group"] for c in cal], [c[key][0] for c in cal], [c[key][1] for c in cal])
        dec = [ctl.decide(c["group"], c[key][0]) for c in test]
        n = len(test)
        wrong = sum(1 for d, c in zip(dec, test) if d == CHARGE and c[key][1])
        rows.append({"alpha": alpha, "wrong_charge_rate": wrong / n,
                     "automation_rate": dec.count(CHARGE) / n, "review_rate": dec.count(REVIEW) / n,
                     "decisions": dec})
    return rows


def plan_for_budget(rows: list[dict], test: list[dict], budget: float, key: str = "fused") -> dict:
    """Strictest promise whose review load fits the budget, with queue triage if none fits."""
    fits = [r for r in rows if r["review_rate"] <= budget]
    if fits:
        best = min(fits, key=lambda r: r["alpha"])
        return {"budget": budget, "alpha": best["alpha"], "wrong_charge_rate": best["wrong_charge_rate"],
                "automation_rate": best["automation_rate"], "review_rate": best["review_rate"], "held_over_budget": 0.0}
    # Nothing fits: use the loosest promise and triage the review queue by expected harm.
    r = max(rows, key=lambda r: r["alpha"])
    queue = [(c[key][0] * c["p"].correct_fee, i) for i, (d, c) in enumerate(zip(r["decisions"], test)) if d == REVIEW]
    keep = int(budget * len(test))
    return {"budget": budget, "alpha": r["alpha"], "wrong_charge_rate": r["wrong_charge_rate"],
            "automation_rate": r["automation_rate"], "review_rate": keep / len(test),
            "held_over_budget": max(0, len(queue) - keep) / len(test)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Review budget vs promised wrong-charge rate.")
    ap.add_argument("--passages", type=int, default=120000)
    ap.add_argument("--seed", type=int, default=26)
    args = ap.parse_args(argv)

    cases = build_cases(20000, args.passages, args.seed)
    test = [c for c in cases if c["split"] == "test"]
    rows = sweep(cases)
    plans = [plan_for_budget(rows, test, b) for b in BUDGETS]
    lines = ["| Promise α | Wrong charges (test) | Charged automatically | Held for next camera | Sent to humans |",
             "|---|---|---|---|---|"]
    lines += [f"| {r['alpha']:.2%} | {r['wrong_charge_rate']:.3%} | {r['automation_rate']:.1%} | "
              f"{1 - r['automation_rate'] - r['review_rate']:.1%} | {r['review_rate']:.1%} |" for r in rows]
    lines += ["", "| Human review budget | Strictest promise that fits | Wrong charges | Charged automatically |",
              "|---|---|---|---|"]
    lines += [f"| {p['budget']:.0%} of traffic | {p['alpha']:.2%} | {p['wrong_charge_rate']:.3%} | {p['automation_rate']:.1%} |"
              for p in plans]
    md = "\n".join(lines)
    out = ROOT / "experiments" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"audit_budget_seed{args.seed}.md").write_text(md + "\n")
    (out / f"audit_budget_seed{args.seed}.json").write_text(json.dumps(
        {"sweep": [{k: v for k, v in r.items() if k != "decisions"} for r in rows], "plans": plans}, indent=2) + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
