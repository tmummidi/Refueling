# Model and release design

## User and decision

Pre-position scarce repair crews across sites for a 72-hour incident horizon. Intended users are analysts and operations researchers
evaluating this decision before committing operational resources.

## Formulation

~~~text
For site i and crew count k, simulate L(i,k,s), the sum of incident weights
times unresolved hours clipped at the 72-hour horizon, on training seed s.
Let l(i,k) be its training mean. Solve:

minimize sum(i,k) l(i,k) x(i,k)
subject to sum(k) x(i,k)=1 for every site,
           sum(i,k) k*x(i,k) <= crew_budget,
           x(i,k) in {0,1}.

The response table uses common incident streams across crew counts. An independent
heldout stream compares the chosen allocation with even allocation. The MILP gap
certifies the finite training-table problem only, not the true stochastic optimum.
~~~

## Data and provenance

Seeded synthetic incident arrivals and repair durations. The generator is the authoritative data source. Parameters
represent hypothetical examples, not estimates from any employer. Seeds,
configuration hashes and package versions are included with executed results.
No pre-existing code from a tutorial or employer is used in the new model.

## Architecture

simulation.py owns synthetic incident generation and SimPy FIFO queues; allocation.py owns the sparse multiple-choice MILP; cli.py keeps training, evaluation and stress seeds disjoint. HiGHS is free and adequate for measured problem sizes.

Dependencies are intentionally small. NumPy handles arrays; SciPy provides
numerical/statistical routines and the free HiGHS solver where applicable.
Distributed infrastructure is not justified by these measurements.

## Evaluation and acceptance

Baseline: Even crew allocation.
Held-out seeds; paired weighted unresolved-hours difference and SLA miss rates; surge stress.
Meaningful tests use analytical results, enumeration, input constraints or
conservation laws. Confidence intervals and primal feasibility are reported,
not inferred from successful process exit alone.

The first release is accepted when installation into a clean environment,
unit tests and an installed CLI example all succeed. The release-validation
log records that check separately from the benchmark timings.

## Scope and limits

Incidents arrive exogenously and can overlap. Loss is weighted unresolved incident-hours, not asset downtime or availability. Repair times are lognormal; site rates and weights are synthetic. Crews remain at assigned sites. No routing, spare inventory, simultaneous asset failure model, staffing shifts, or confidential infrastructure topology is represented.

The doubled-arrival stress case still creates heavy backlog. Optimizing the training response table does not guarantee an SLA. Incidents younger than the SLA threshold at horizon end are reported as pending rather than treated as successes.

## Resource budget

One process, train 4-8 seeds, test 16-32 seeds, 30s solve cap; larger configuration unexecuted. The published benchmark is serial and uses three increasing
workloads. Very large configurations can exceed laptop memory or practical
solver time. Only the recorded configurations were executed.

## Extensions

Add shift calendars and skill compatibility with conservation tests. Evaluate cross-site dispatch against static allocation. Estimate parameter uncertainty from a properly licensed incident dataset. Add independent training replications to quantify allocation-selection uncertainty.

## Method references

- SciPy 1.13 MILP API and result status: https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.optimize.milp.html
- SimPy shared resources: https://simpy.readthedocs.io/en/stable/simpy_intro/shared_resources.html
- NIST reliability estimation with censoring: https://www.itl.nist.gov/div898/handbook/apr/section4/apr413.htm
- SciPy Gamma shape/scale parameterization: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.gamma.html

References describe underlying methods. Results in this repository come from
the included implementation and executable configurations.
