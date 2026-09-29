"""Synthetic incident queues. Loss is unresolved incident-hours, not uptime."""
from dataclasses import dataclass
import numpy as np
import simpy


@dataclass(frozen=True)
class Incident:
    arrival: float
    repair_hours: float
    weight: float = 1.0


def generate(seed, sites, horizon=72.0, surge=1.0):
    if sites < 1 or horizon <= 0 or surge <= 0:
        raise ValueError("Positive sites, horizon and surge required")
    rng = np.random.default_rng(seed)
    # Persistent site heterogeneity makes the allocation decision nontrivial.
    rates = np.resize(np.array([.15, .4, .8, 1.1]), sites) * surge
    jobs = []
    for i, rate in enumerate(rates):
        arrivals = np.sort(rng.uniform(0, horizon, rng.poisson(rate*horizon)))
        durations = rng.lognormal(mean=np.log(2.0)-.5*.5**2, sigma=.5, size=len(arrivals))
        jobs.append([Incident(float(a), float(d), 1+(i % 3)) for a, d in zip(arrivals, durations)])
    return jobs


def simulate(jobs, crews, horizon=72.0, sla_hours=6.0):
    """Integrate each incident's unresolved time, clipping at the horizon.

    An incident finishing exactly at the horizon is counted as completed.
    Incidents too young to observe their SLA outcome are reported separately.
    """
    if not isinstance(crews, (int, np.integer)) or crews < 0 or horizon <= 0 or sla_hours <= 0:
        raise ValueError("Invalid crews, horizon or SLA")
    if any(not np.isfinite([j.arrival, j.repair_hours, j.weight]).all()
           or not 0 <= j.arrival < horizon or j.repair_hours <= 0 or j.weight < 0 for j in jobs):
        raise ValueError("Incident must arrive in horizon with positive repair time and nonnegative weight")
    env = simpy.Environment()
    completion = np.full(len(jobs), np.inf)
    resource = simpy.Resource(env, capacity=crews) if crews else None

    def incident(index, job):
        yield env.timeout(job.arrival)
        with resource.request() as request:
            yield request
            yield env.timeout(job.repair_hours)
            completion[index] = env.now

    if crews:
        for i, job in enumerate(jobs):
            env.process(incident(i, job))
        env.run(until=np.nextafter(float(horizon), np.inf))
    arrivals = np.array([j.arrival for j in jobs])
    unresolved = np.minimum(completion, horizon)-arrivals
    weights = np.array([j.weight for j in jobs])
    mature = arrivals+sla_hours <= horizon
    return {
        "arrivals": len(jobs),
        "completed": int(np.sum(completion <= horizon)),
        "unfinished": int(np.sum(completion > horizon)),
        "weighted_unresolved_hours": float(unresolved @ weights),
        "sla_observed": int(mature.sum()),
        "sla_missed": int(np.sum(mature & (completion-arrivals > sla_hours))),
        "sla_pending": int((~mature).sum()),
    }


def evaluate(jobs_by_site, allocation, horizon, sla_hours):
    if len(jobs_by_site) != len(allocation):
        raise ValueError("One allocation required per site")
    rows = [simulate(j, int(c), horizon, sla_hours) for j, c in zip(jobs_by_site, allocation)]
    return {k: sum(r[k] for r in rows) for k in rows[0]}
