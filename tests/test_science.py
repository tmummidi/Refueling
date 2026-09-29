import itertools
import unittest
import numpy as np
from continuity.simulation import Incident, simulate, generate
from continuity.allocation import optimize, even_allocation
from continuity.cli import run, DEFAULT


class QueueTests(unittest.TestCase):
    def test_hand_computed_fifo_queue(self):
        jobs = [Incident(0, 2), Incident(1, 2)]
        r = simulate(jobs, 1, horizon=10, sla_hours=2)
        self.assertEqual(r["weighted_unresolved_hours"], 5)
        self.assertEqual(r["sla_missed"], 1)
        self.assertEqual(r["completed"], 2)

    def test_zero_crews_and_horizon_censoring(self):
        r = simulate([Incident(1, 4, 2), Incident(9, 4)], 0, 10, 2)
        self.assertEqual(r["weighted_unresolved_hours"], 19)
        self.assertEqual(r["unfinished"], 2)
        self.assertEqual(r["sla_pending"], 1)

    def test_exact_boundary_completion(self):
        self.assertEqual(simulate([Incident(0, 10)], 1, 10)["completed"], 1)

    def test_conservation_and_more_crews(self):
        jobs = generate(19, 1)[0]
        losses = []
        for c in range(5):
            r = simulate(jobs, c)
            self.assertEqual(r["arrivals"], r["completed"]+r["unfinished"])
            self.assertEqual(r["arrivals"], r["sla_observed"]+r["sla_pending"])
            losses.append(r["weighted_unresolved_hours"])
        self.assertTrue(np.all(np.diff(losses) <= 1e-9))

    def test_reject_invalid_jobs(self):
        with self.assertRaises(ValueError):
            simulate([Incident(0, -1)], 1)
        self.assertEqual(simulate([], 0)["weighted_unresolved_hours"], 0)


class AllocationTests(unittest.TestCase):
    def test_matches_exhaustive_optimum(self):
        loss = np.array([[20, 5, 3], [50, 30, 4], [10, 3, 1]])
        a, r = optimize(loss, 3)
        exact = min(sum(loss[i,k] for i,k in enumerate(x))
                    for x in itertools.product(range(3), repeat=3) if sum(x) <= 3)
        self.assertAlmostEqual(r["objective"], exact)
        self.assertLessEqual(sum(a), 3)
        self.assertEqual(r["mip_gap"], 0)

    def test_budget_validation(self):
        with self.assertRaises(ValueError):
            even_allocation(2, 8, 3)
        with self.assertRaises(ValueError):
            optimize([[1,0]], -1)

    def test_seed_partitions_and_small_pipeline(self):
        r = run(dict(DEFAULT, sites=2, budget=2, train_seeds=2, test_seeds=3))
        self.assertFalse(set(r["training_seeds"]) & set(r["test_seeds"]))
        self.assertEqual(len(r["heldout"]["replications"]), 3)
        self.assertLessEqual(sum(r["allocation"]), 2)
