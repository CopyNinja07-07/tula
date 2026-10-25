"""Checks that the risk controller keeps its promise on data where we know the truth."""
import random
import unittest

from tula.crc import CHARGE, HOLD, REVIEW, GroupController, binom_ucb, crc_threshold, min_group_size


def draw(n, rng):
    """Scores where higher means more likely wrong; 8% of passages are wrong overall."""
    out = []
    for _ in range(n):
        wrong = rng.random() < 0.08
        out.append((min(1.0, max(0.0, rng.gauss(0.6 if wrong else 0.25, 0.15))), wrong))
    return out


def test_risk(tau, test):
    return sum(1 for s, w in test if tau is not None and s <= tau and w) / len(test)


class CRCTest(unittest.TestCase):
    def test_average_risk_stays_under_alpha(self):
        rng, alpha, risks = random.Random(0), 0.02, []
        for _ in range(300):
            cal, test = draw(400, rng), draw(2000, rng)
            risks.append(test_risk(crc_threshold([s for s, _ in cal], [w for _, w in cal], alpha), test))
        self.assertLessEqual(sum(risks) / len(risks), alpha)

    def test_high_probability_mode(self):
        rng, alpha, delta, over = random.Random(1), 0.02, 0.1, 0
        for _ in range(300):
            cal, test = draw(400, rng), draw(20000, rng)
            tau = crc_threshold([s for s, _ in cal], [w for _, w in cal], alpha, delta)
            over += test_risk(tau, test) > alpha
        self.assertLessEqual(over / 300, delta)

    def test_small_group_is_not_certified(self):
        self.assertEqual(min_group_size(0.01), 99)
        self.assertIsNone(crc_threshold([0.1] * 50, [False] * 50, 0.01))
        self.assertIsNotNone(crc_threshold([0.1] * 99, [False] * 99, 0.01))

    def test_ucb_matches_known_value(self):
        # 0 errors in 100 trials, 90% one-sided bound: 1 - 0.1 ** (1/100) = 0.0228
        self.assertAlmostEqual(binom_ucb(0, 100, 0.1), 1 - 0.1 ** 0.01, places=4)

    def test_controller_decisions(self):
        rng = random.Random(2)
        data = draw(3000, rng)
        ctl = GroupController(0.02).fit(["big"] * 3000 + ["tiny"] * 10, [s for s, _ in data] + [0.0] * 10,
                                        [w for _, w in data] + [False] * 10)
        self.assertTrue(ctl.certified("big"))
        self.assertFalse(ctl.certified("tiny"))
        self.assertEqual(ctl.decide("big", 0.0), CHARGE)
        self.assertEqual(ctl.decide("big", 1.0), REVIEW)
        self.assertEqual(ctl.decide("tiny", 0.0), HOLD)  # no certificate, no automatic charge


if __name__ == "__main__":
    unittest.main()
