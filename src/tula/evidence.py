"""Evidence check: compare the readers with the FASTag and registry records.

Plain code, no model, so it is the only place that sees both readers' answers
(whitepaper Section 3.1). It decides who would be billed and turns the evidence
into one disagreement score s in [0, 1]. The weights are hand-set on purpose:
the safety claim comes from calibrating the cut-off, not from the score, so a
weaker score costs automation, not safety (Section 3.2).
"""
from __future__ import annotations

from dataclasses import dataclass

from tula.simulate import TOLL_CLASSES

WEIGHTS = {
    "plate_disagree": 0.35,   # Reader A vs Reader B
    "tag_mismatch": 0.35,     # tag's registered plate vs what the cameras read
    "type_mismatch": 0.25,    # vehicle seen vs the billed vehicle's toll class
    "colour_mismatch": 0.15,
    "make_mismatch": 0.15,
    "low_confidence": 0.20,
    "no_tag": 0.10,
}


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def plate_gap(a: str | None, b: str | None) -> float:
    """0 when two plate strings match, 1 when either is missing or they share nothing."""
    if not a or not b:
        return 1.0
    return min(1.0, edit_distance(a, b) / max(len(a), len(b)))


@dataclass
class Evidence:
    target: str | None        # vehicle_id that would be billed, None if nobody can be
    fee: int | None
    signals: dict
    score: float


def check(read_a: dict | None, read_b: dict | None, tag_read: str | None, tag_class: str | None,
          by_tag: dict, by_plate: dict, use_a: bool = True, use_b: bool = True) -> Evidence:
    """Fuse whichever readers are switched on into a billing target and a score."""
    a = read_a if use_a else None
    b = read_b if use_b else None
    reads = [r for r in (a, b) if r and r.get("plate_text")]
    best = max(reads, key=lambda r: r["plate_confidence"])["plate_text"] if reads else None

    if tag_read is not None:
        target = by_tag[tag_read]
        billed_class = tag_class or target.tag_class
    else:
        target = by_plate.get(best) if best else None
        billed_class = target.toll_class if target else None
    fee = TOLL_CLASSES[billed_class]["fee"] if target else None

    sig = {k: 0.0 for k in WEIGHTS}
    if a and b:
        sig["plate_disagree"] = plate_gap(a.get("plate_text"), b.get("plate_text"))
    confs = [r["plate_confidence"] for r in (a, b) if r]
    sig["low_confidence"] = 1 - min(confs) if confs else 1.0
    sig["no_tag"] = float(tag_read is None)
    if target is not None:
        sig["tag_mismatch"] = plate_gap(best, target.plate) if tag_read is not None else 0.0
        if b and "vehicle_type" in b:
            allowed = TOLL_CLASSES[billed_class]["vehicle_types"]
            sig["type_mismatch"] = float(b["vehicle_type"] not in allowed)
            sig["colour_mismatch"] = float(b["colour"] != target.colour)
            sig["make_mismatch"] = float(b["make"] != target.make)

    score = 1.0 if target is None else min(1.0, sum(WEIGHTS[k] * v for k, v in sig.items()))
    return Evidence(target.vehicle_id if target else None, fee, sig, round(score, 4))


class LearnedScore:
    """Logistic regression on the evidence signals, fit on its own split.

    Learning the weights is allowed because the cut-off is calibrated on
    different passages afterwards, so the guarantee still holds. It only
    changes how much traffic can be charged automatically.
    """

    def __init__(self, keys: list[str] | None = None):
        self.keys = keys or list(WEIGHTS)
        self.w = [0.0] * len(self.keys)
        self.b = 0.0

    def _x(self, signals: dict) -> list[float]:
        return [signals.get(k, 0.0) for k in self.keys]

    def fit(self, signals: list[dict], wrong: list[bool], epochs: int = 300, lr: float = 0.5):
        import math
        xs, ys, n = [self._x(s) for s in signals], [float(w) for w in wrong], len(signals)
        pos = sum(ys) or 1.0
        cw = {1.0: n / (2 * pos), 0.0: n / (2 * max(1.0, n - pos))}  # balance rare wrong cases
        for _ in range(epochs):
            gw, gb = [0.0] * len(self.w), 0.0
            for x, y in zip(xs, ys):
                z = self.b + sum(wi * xi for wi, xi in zip(self.w, x))
                p = 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
                g = (p - y) * cw[y]
                gb += g
                for i, xi in enumerate(x):
                    gw[i] += g * xi
            self.b -= lr * gb / n
            self.w = [wi - lr * gi / n for wi, gi in zip(self.w, gw)]
        return self

    def score(self, signals: dict, target_found: bool = True) -> float:
        import math
        if not target_found:
            return 1.0
        z = self.b + sum(wi * xi for wi, xi in zip(self.w, self._x(signals)))
        return round(1 / (1 + math.exp(-max(-30.0, min(30.0, z)))), 6)
