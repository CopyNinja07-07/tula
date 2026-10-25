"""Conformal risk control with one cut-off per group (whitepaper Section 3.3-3.4).

Each calibration passage has a disagreement score s (higher = more doubt)
and a flag w: would charging it be a wrong charge? Charging everything with
s <= tau gives the loss L(tau) = 1[s <= tau] * w, which never decreases as
tau grows. Conformal risk control (Angelopoulos et al., arXiv 2208.02814)
picks the largest tau with

    n/(n+1) * mean_i L_i(tau) + 1/(n+1) <= alpha

and then the expected wrong-charge rate on new, exchangeable passages is at
most alpha. A group too small to pass even at tau = -inf (n < 1/alpha - 1)
gets no cut-off: no certificate, no automatic charge.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Hashable, Iterable, Sequence

CHARGE, HOLD, REVIEW = "charge", "hold", "review"


def binom_ucb(k: int, n: int, delta: float) -> float:
    """Clopper-Pearson upper bound: the largest p with P(Bin(n, p) <= k) >= delta."""
    if k >= n:
        return 1.0

    def cdf(p: float) -> float:
        term = (1 - p) ** n  # P(X = 0), then walk up with the pmf ratio
        total = term
        for i in range(k):
            term *= (n - i) / (i + 1) * p / (1 - p)
            total += term
        return total

    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) >= delta else (lo, mid)
    return lo


def max_errors_ucb(n: int, alpha: float, delta: float) -> int:
    """Most wrong charges among n calibration passages that still keep the UCB <= alpha (-1 if none)."""
    k = -1
    while k + 1 <= n and binom_ucb(k + 1, n, delta) <= alpha:
        k += 1
    return k


def crc_threshold(scores: Sequence[float], wrong: Sequence[bool], alpha: float,
                  delta: float | None = None) -> float | None:
    """Largest tau whose risk bound is <= alpha, or None if the group can't be certified.

    delta=None is plain conformal risk control: the wrong-charge rate is <= alpha on
    average over calibration draws. With delta (say 0.1) it is the high-probability
    version (Learn-then-Test style, Clopper-Pearson bound): the true rate is <= alpha
    with probability at least 1 - delta, for this calibration set.
    """
    n = len(scores)
    if delta is None:
        if n == 0 or (1 / (n + 1)) > alpha:
            return None
        budget = alpha * (n + 1) - 1  # allowed number of wrong charges among calibration passages
    else:
        budget = max_errors_ucb(n, alpha, delta) if n else -1
        if budget < 0:
            return None
    pairs = sorted(zip(scores, wrong))
    best, errors, i = -math.inf, 0, 0
    while i < n:  # walk up through distinct scores; ties enter together
        j, s = i, pairs[i][0]
        while j < n and pairs[j][0] == s:
            errors += pairs[j][1]
            j += 1
        if errors > budget:
            break
        best, i = s, j
    return best


def min_group_size(alpha: float) -> int:
    return math.ceil(1 / alpha - 1)


@dataclass
class GroupController:
    """Per-group cut-offs: charge below tau_charge, hold below tau_hold, else review."""
    alpha: float
    alpha_hold: float | None = None   # looser target for the hold band; default 5 * alpha
    delta: float | None = None        # None: in-expectation CRC; e.g. 0.1: holds with 90% probability
    taus: dict = field(default_factory=dict)       # group -> (tau_charge, tau_hold)
    sizes: dict = field(default_factory=dict)

    def fit(self, groups: Iterable[Hashable], scores: Iterable[float], wrong: Iterable[bool]):
        alpha_hold = self.alpha_hold or min(1.0, 5 * self.alpha)
        buckets: dict = defaultdict(lambda: ([], []))
        for g, s, w in zip(groups, scores, wrong):
            buckets[g][0].append(s)
            buckets[g][1].append(bool(w))
        for g, (s, w) in buckets.items():
            self.sizes[g] = len(s)
            self.taus[g] = (crc_threshold(s, w, self.alpha, self.delta), crc_threshold(s, w, alpha_hold, self.delta))
        return self

    def certified(self, group: Hashable) -> bool:
        tau = self.taus.get(group, (None, None))[0]
        return tau is not None and tau > -math.inf

    def decide(self, group: Hashable, score: float) -> str:
        tau_charge, tau_hold = self.taus.get(group, (None, None))
        if tau_charge is not None and score <= tau_charge:
            return CHARGE
        if tau_hold is not None and score <= tau_hold:
            return HOLD
        # Uncertified groups never auto-charge; low-doubt passages wait for more evidence.
        if not self.certified(group) and score <= 0.25:
            return HOLD
        return REVIEW
