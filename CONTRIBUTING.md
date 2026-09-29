# Contributing

Create a virtual environment, run python -m pip install ., then
python -m unittest discover -s tests -v.
Use PYTHONPATH=src during local source edits, or reinstall the package.
Keep a reproducer and an analytical, enumeration, or invariant-based test for
scientific changes. Report seeds, configuration and solver status with results.
Run python -m continuity --benchmark --output results/benchmark.json for scale evidence.
Do not commit credentials, employer data, or results from unexecuted experiments.
Do not silently change a data generator to improve a benchmark.

Extension priorities and model limitations are in docs/design.md.
