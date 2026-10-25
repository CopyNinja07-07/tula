"""Smoke tests for the review-budget sweep and the recursive dispute loop."""
import unittest

from tula.audit import plan_for_budget
from tula.feedback import run


class LoopTest(unittest.TestCase):
    def test_budget_picks_strictest_promise_that_fits(self):
        rows = [{"alpha": 0.002, "review_rate": 0.12, "wrong_charge_rate": 0.001, "automation_rate": 0.5},
                {"alpha": 0.01, "review_rate": 0.04, "wrong_charge_rate": 0.008, "automation_rate": 0.9}]
        self.assertEqual(plan_for_budget(rows, [], 0.05)["alpha"], 0.01)
        self.assertEqual(plan_for_budget(rows, [], 0.20)["alpha"], 0.002)

    def test_feedback_loop_runs_and_reports_both_systems(self):
        report = run(rounds=2, per_round=3000, alpha=0.05, audit_rate=0.1, seed=3)
        self.assertEqual(len(report["history"]), 2)
        for row in report["history"]:
            for name in ("naive", "tula"):
                self.assertGreaterEqual(row[name]["true_wrong_rate"], 0)


if __name__ == "__main__":
    unittest.main()
