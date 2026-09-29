# Dependencies and provenance

NumPy (BSD-3-Clause) and SciPy (BSD-3-Clause) are installed dependencies, not
vendored code. SciPy's bundled HiGHS solver provides free LP/MIP capability and
retains its upstream license notices. Packaging uses setuptools (MIT) and wheel
(MIT). Tests use Python's standard library. CI uses GitHub's official checkout
and setup-python actions (MIT).
SimPy (MIT) implements the event queue and shared resources.

All new implementations and default benchmark data are independent work
created for this portfolio. No employer code, operational data, architecture,
impact metrics, or confidential incident distributions are reproduced.
Synthetic parameters are explanatory assumptions, not industry estimates.
