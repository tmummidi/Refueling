"""Allocation is fitted on training seeds, then evaluated on unseen incidents."""
import numpy as np
from .simulation import generate, simulate, evaluate
from .allocation import optimize, even_allocation
from .evidence import cli, paired_interval

DEFAULT = dict(sites=8, budget=16, max_crews=4, horizon=72.0, sla_hours=6.0,
               train_seeds=8, test_seeds=32, seed=20260929, surge=1.0)
SCALES = [dict(sites=n, budget=2*n, train_seeds=4, test_seeds=16) for n in (4, 16, 64)]


def run(c):
    """Generate incidents, fit crew allocation, evaluate and stress-test."""
    n, h = c["sites"], c["horizon"]
    if c["train_seeds"] < 1 or c["test_seeds"] < 2 or c["max_crews"] < 1:
        raise ValueError("Positive training replications and at least two test replications required")
    baseline = even_allocation(n, c["budget"], c["max_crews"])
    table = np.zeros((n, c["max_crews"]+1))
    seed_sequences = np.random.SeedSequence(c["seed"]).spawn(3)
    train_seeds = [int(x) for x in seed_sequences[0].generate_state(c["train_seeds"])]
    test_seeds = [int(x) for x in seed_sequences[1].generate_state(c["test_seeds"])]
    stress_seeds = [int(x) for x in seed_sequences[2].generate_state(c["test_seeds"])]
    simulated_incidents = 0
    for seed in train_seeds:
        jobs = generate(seed, n, h, c["surge"])
        for i in range(n):
            for k in range(c["max_crews"]+1):
                table[i, k] += simulate(jobs[i], k, h, c["sla_hours"])["weighted_unresolved_hours"]
                simulated_incidents += len(jobs[i])
    table /= len(train_seeds)
    allocation, solver = optimize(table, c["budget"])

    def compare(seeds, multiplier):
        rows = []
        for seed in seeds:
            jobs = generate(seed, n, h, multiplier)
            b = evaluate(jobs, baseline, h, c["sla_hours"])
            o = evaluate(jobs, allocation, h, c["sla_hours"])
            rows.append({"seed": seed, "baseline": b, "optimized": o})
        differences = [r["baseline"]["weighted_unresolved_hours"]-r["optimized"]["weighted_unresolved_hours"] for r in rows]
        means = {}
        for name in ("baseline", "optimized"):
            means[name] = {k: float(np.mean([r[name][k] for r in rows])) for k in rows[0][name]}
        return {"means": means, "baseline_minus_optimized": paired_interval(differences),
                "replications": rows}
    test = compare(test_seeds, c["surge"])
    stress = compare(stress_seeds, 2*c["surge"])
    simulated_incidents += 2*sum(r["baseline"]["arrivals"] for result in (test, stress) for r in result["replications"])
    return {"work_units":{"count":simulated_incidents,"unit":"incident executions"}, "project": "continuity", "data": "independent synthetic incidents",
            "training_seeds": train_seeds, "test_seeds": test_seeds, "stress_seeds": stress_seeds,
            "allocation": allocation.tolist(), "baseline_allocation": baseline.tolist(),
            "training_response_table": table.tolist(), "solver": solver,
            "heldout": test, "double_arrival_stress": stress,
            "simulated_incident_executions": simulated_incidents}


def main():
    cli(run, DEFAULT, SCALES, "continuity")
