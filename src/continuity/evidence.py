"""Reproducible single-process evidence; no remote services or telemetry."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np
from scipy.stats import t


def paired_interval(differences):
    """Student-t interval for independent paired replication differences."""
    values = np.asarray(differences, dtype=float)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("At least two finite paired replications required")
    mean = float(values.mean())
    half = float(t.ppf(.975, len(values)-1) * values.std(ddof=1) / np.sqrt(len(values)))
    return {"mean": mean, "lower_95": mean-half, "upper_95": mean+half,
            "n": len(values), "method": "paired replication Student-t"}


def metadata(config):
    versions = {}
    for name in ("numpy", "scipy", "simpy"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    cpu = platform.processor()
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    quotas = {}
    for p in ("/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/memory.max"):
        if Path(p).exists():
            quotas[Path(p).name] = Path(p).read_text().strip()
    return {"python": sys.version, "platform": platform.platform(),
            "cpu_model": cpu, "logical_cpus": os.cpu_count(),
            "cpu_affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "cgroup_limits": quotas, "versions": versions,
            "thread_environment": {x: os.environ.get(x) for x in
                ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
            "config": config,
            "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()}


def peak_rss_mib():
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value / (1024**2 if sys.platform == "darwin" else 1024)
    except ImportError:
        return None


def cli(run, defaults, scales, package):
    parser = argparse.ArgumentParser(description=run.__doc__)
    parser.add_argument("--config", type=Path, help="JSON overrides for default configuration")
    parser.add_argument("--output", type=Path, default=Path("results/demo.json"))
    parser.add_argument("--benchmark", action="store_true", help="Run scale cases in fresh processes")
    args = parser.parse_args()
    config = dict(defaults)
    if args.config:
        overrides = json.loads(args.config.read_text())
        unknown = set(overrides)-set(config)
        if unknown:
            parser.error("Unknown config keys: " + ", ".join(sorted(unknown)))
        config.update(overrides)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.benchmark:
        rows = []
        for index, overrides in enumerate(scales):
            case = dict(config, **overrides)
            cp = args.output.parent / f"case-{index}.config.json"
            rp = args.output.parent / f"case-{index}.json"
            cp.write_text(json.dumps(case, indent=2))
            start = time.perf_counter()
            process = subprocess.run([sys.executable, "-m", package, "--config", str(cp),
                                      "--output", str(rp)], capture_output=True, text=True)
            elapsed = time.perf_counter()-start
            row = {"case": index, "cold_process_seconds": elapsed, "exit_code": process.returncode,
                   "config": case}
            if process.returncode == 0:
                row["result"] = json.loads(rp.read_text())
            else:
                row["error"] = process.stderr[-2000:]
            rows.append(row)
        report = {"status": "executed", "measurement": "Fresh process per scale case; runtime includes data generation, fit/solve and evaluation; RSS includes imports",
                  "cases": rows}
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False))
        print(json.dumps({"output": str(args.output), "passed_cases": sum(r["exit_code"] == 0 for r in rows)}))
        if any(r["exit_code"] for r in rows):
            raise SystemExit(1)
        return
    start = time.perf_counter()
    result = run(config)
    elapsed = time.perf_counter()-start
    result["evidence"] = dict(metadata(config), status="executed",
        runtime_seconds=elapsed, peak_rss_mib=peak_rss_mib(),
        memory_method="process peak RSS via getrusage; unavailable on Windows")
    units = result.get("work_units")
    if units:
        result["evidence"]["throughput_per_second"] = units["count"]/elapsed
        result["evidence"]["throughput_unit"] = units["unit"]
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({"output": str(args.output), "runtime_seconds": round(elapsed, 4)}))
