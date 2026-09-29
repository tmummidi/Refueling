# Refueling: infrastructure continuity decisions

**Decision:** Pre-position scarce repair crews across sites for a 72-hour incident horizon.

[![Visual evidence checks](https://github.com/tmummidi/Refueling/actions/workflows/visuals.yml/badge.svg)](https://github.com/tmummidi/Refueling/actions/workflows/visuals.yml)

### See the decision play out

[![Synchronized replay: the same incidents under even and optimized crew allocation](https://raw.githubusercontent.com/tmummidi/Refueling/visual-assets/preview.gif)](https://github.com/tmummidi/Refueling/blob/visual-assets/continuity_demo.mp4)

**[Watch or download the 60-second video](https://github.com/tmummidi/Refueling/blob/visual-assets/continuity_demo.mp4)** ·
[Run the renderer](visuals/README.md) ·
[Inspect event logs](https://github.com/tmummidi/Refueling/blob/visual-assets/continuity_demo.json) ·
[Check source revision](https://github.com/tmummidi/Refueling/blob/visual-assets/manifest.json)

The animation replays one held-out **8-site** scenario with identical incidents
and a shared clock under both policies. Busy/assigned crew counts and waiting
queues come from actual SimPy events. The separate **64-site** chart below
summarizes 16 independent evaluation replications. All data are synthetic.

![Measured comparison across 16 held-out replications](https://raw.githubusercontent.com/tmummidi/Refueling/visual-assets/comparison.svg)

Changes to the model or renderer trigger checks and regenerate these visuals
from the same checkout. Published media records the source commit and file
hashes; the last successful version remains visible if a newer build fails.
The video is captioned and silent; the generator supports optional narration.

Queues become nonlinear near saturation. Uniform staffing can leave high-load sites backlogged while crews at quieter sites remain underused.

This is a working v0.1 research engineering release, with synthetic data, a free
solver path, scientific tests, and recorded local measurements. It is independent
portfolio work. Employer systems and impact numbers are not benchmark evidence.

## Run

Python 3.10 or 3.12 is the supported CI target; the recorded local verification
used Python 3.12.14.

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m continuity --output results/demo.json
python -m unittest discover -s tests -v
python -m continuity --benchmark --output results/benchmark.json
~~~

On Windows activate with .venv\Scripts\activate. The core has no paid service,
proprietary solver license, external dataset download, or GPU requirement.
Package dependencies and build tools are pinned in pyproject.toml.

To use a configuration:

~~~bash
python -m continuity --config configs/ci.json --output results/small.json
~~~

Change sites, budget, max_crews, train_seeds, test_seeds, horizon, sla_hours and surge in a JSON configuration. Arrays in the result expose the response table and both allocations.

## Implementation

simulation.py owns synthetic incident generation and SimPy FIFO queues; allocation.py owns the sparse multiple-choice MILP; cli.py keeps training, evaluation and stress seeds disjoint. HiGHS is free and adequate for measured problem sizes.

Baseline: Even crew allocation. Evaluation: Held-out seeds; paired weighted unresolved-hours difference and SLA miss rates; surge stress.
The full mathematical specification is in [docs/design.md](docs/design.md).

## Executed measurements

| Workload | Runtime (s) | Peak RSS (MiB) | Measured quality |
|---|---:|---:|---|
| 4 sites, 8 crews | 0.247 | 88.3 | 27.7% fewer weighted unresolved hours; MIP gap 0.0% |
| 16 sites, 32 crews | 0.936 | 88.3 | 37.1% fewer weighted unresolved hours; MIP gap 0.0% |
| 64 sites, 128 crews | 3.940 | 90.0 | 42.8% fewer weighted unresolved hours; MIP gap 0.0% |

The 64-site case reduced weighted unresolved incident-hours by 11,630.5; the paired 95% interval was [10,548.1, 12,712.9] over 16 independent test replications. Doubling arrival rates still created substantial backlog.

Measurements ran on an AMD EPYC 9V74 host in a Linux container with an 8-vCPU,
8-GiB cgroup limit. These are laptop-sized workloads, not laptop hardware
measurements. One fresh process was used per scale case. Runtime includes
generation, fitting/optimization and evaluation, but excludes Python imports;
the report also records cold-process time. Peak RSS includes imports.
BLAS/OpenMP thread environment defaults were set to one; actual solver thread
utilization was not measured. No distributed scaling or parallel speedup is claimed.
Single timing observations are not latency distributions.

Raw seeds, versions, configurations, peak RSS, solver/statistical evidence and
derived throughput are in [results/benchmark.json](results/benchmark.json).
The throughput numerator is project-specific and includes only the declared work
units; it must not be compared across projects.

## Assumptions and failure cases

Incidents arrive exogenously and can overlap. Loss is weighted unresolved incident-hours, not asset downtime or availability. Repair times are lognormal; site rates and weights are synthetic. Crews remain at assigned sites. No routing, spare inventory, simultaneous asset failure model, staffing shifts, or confidential infrastructure topology is represented.

The doubled-arrival stress case still creates heavy backlog. Optimizing the training response table does not guarantee an SLA. Incidents younger than the SLA threshold at horizon end are reported as pending rather than treated as successes.

## Reproducibility and contribution

Data are generated from explicit seeds. Training and heldout scenarios are
separate; confidence intervals describe evaluation sampling variability, not
uncertainty in all model assumptions. Larger configurations in
configs/larger-unexecuted.json are **unexecuted** and are not performance claims.
No hypotheses are presented as measurements.

See [CONTRIBUTING.md](CONTRIBUTING.md), [THIRD_PARTY.md](THIRD_PARTY.md), and
[LICENSE](LICENSE). v0.1 covers the complete single-machine vertical slice above.
It is not a production deployment.
