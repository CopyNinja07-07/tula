"""Checks that the simulated layers keep their ground truth straight."""
import random
import unittest

from tula.simulate import TOLL_CLASSES, make_passages, make_registry, summarise


class SimulateTest(unittest.TestCase):
    def setUp(self):
        rng = random.Random(1)
        self.vehicles = make_registry(300, rng)
        self.passages = make_passages(self.vehicles, 4000, rng)
        self.by_id = {v.vehicle_id: v for v in self.vehicles}

    def test_registry_is_unique(self):
        self.assertEqual(len({v.plate for v in self.vehicles}), len(self.vehicles))
        self.assertEqual(len({v.tag_id for v in self.vehicles}), len(self.vehicles))

    def test_same_seed_same_data(self):
        a = make_registry(50, random.Random(7))
        b = make_registry(50, random.Random(7))
        self.assertEqual(a, b)

    def test_clean_passages_are_never_wrong(self):
        clean = [p for p in self.passages if p.scenario == "clean"]
        self.assertTrue(clean)
        self.assertFalse(any(p.naive_wrong_charge for p in clean))

    def test_attacks_fool_the_naive_biller(self):
        for scenario in ("tag_swap", "cloned_plate", "wrong_class"):
            rows = [p for p in self.passages if p.scenario == scenario]
            self.assertTrue(rows, scenario)
            self.assertTrue(all(p.naive_wrong_charge for p in rows), scenario)

    def test_cloned_plate_bills_the_victim(self):
        for p in (p for p in self.passages if p.scenario == "cloned_plate"):
            self.assertNotEqual(p.naive_account, p.true_vehicle_id)
            self.assertEqual(self.by_id[p.naive_account].plate, p.shown_plate)

    def test_correct_fee_matches_true_class(self):
        for p in self.passages:
            self.assertEqual(p.correct_fee, TOLL_CLASSES[self.by_id[p.true_vehicle_id].toll_class]["fee"])

    def test_summary_counts(self):
        s = summarise(self.passages)
        self.assertEqual(s["passages"], 4000)
        self.assertEqual(sum(v["passages"] for v in s["by_scenario"].values()), 4000)


if __name__ == "__main__":
    unittest.main()
