#!/usr/bin/env python3
"""
Measure Raspberry Pi 5 power while a command runs (e.g. one advisor.py call).

Uses `vcgencmd pmic_read_adc`, which reports voltage and current for the Pi's own
supply rails (CPU, RAM, I/O). It does NOT include the AI HAT+ 2 or USB devices,
so this measures the CPU-side cost of each model. For HAT power, use a USB-C meter.

Usage:
    MODEL=qwen2.5-instruct:1.5b python3 power_log.py --label qwen -- python3 advisor.py
    MODEL=deepseek_r1_distill_qwen:1.5b python3 power_log.py --label deepseek -- python3 advisor.py

Steps: measures idle baseline -> runs the command while sampling -> prints a summary
and writes every sample to power_logs/<label>_<time>.csv.
"""

import argparse
import csv
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

LINE_RE = re.compile(r"(\S+)\s+(current|volt)\(\d+\)=([\d.]+)[AV]")


def read_power_w() -> float:
    """Sum of V*I over every rail that reports both a current and a voltage."""
    out = subprocess.run(["vcgencmd", "pmic_read_adc"], capture_output=True, text=True, check=True).stdout
    currents, volts = {}, {}
    for name, kind, value in LINE_RE.findall(out):
        rail = name.rsplit("_", 1)[0]  # "VDD_CORE_A" -> "VDD_CORE"
        (currents if kind == "current" else volts)[rail] = float(value)
    return sum(currents[r] * volts[r] for r in currents if r in volts)


def sample(duration_s: float | None, period_s: float, phase: str, rows: list, stop: threading.Event | None = None):
    end = time.monotonic() + duration_s if duration_s else None
    while not (stop and stop.is_set()) and not (end and time.monotonic() >= end):
        t = time.monotonic()
        rows.append((t, phase, read_power_w()))
        time.sleep(max(0.0, period_s - (time.monotonic() - t)))


def energy_j(samples: list, baseline_w: float = 0.0) -> float:
    """Trapezoidal integral of (P - baseline) over time."""
    return sum(((a[2] + b[2]) / 2 - baseline_w) * (b[0] - a[0]) for a, b in zip(samples, samples[1:]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="name for this run, e.g. qwen or deepseek")
    ap.add_argument("--baseline", type=float, default=10.0, help="idle seconds to measure first (default 10)")
    ap.add_argument("--period", type=float, default=0.25, help="seconds between samples (default 0.25)")
    ap.add_argument("command", nargs=argparse.REMAINDER, help="command to run, after --")
    args = ap.parse_args()
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not cmd:
        sys.exit("Give a command after --, e.g. -- python3 advisor.py")

    rows: list = []
    print(f"Measuring idle baseline for {args.baseline:.0f}s, keep the Pi otherwise idle...")
    sample(args.baseline, args.period, "baseline", rows)
    baseline = [r for r in rows if r[1] == "baseline"]
    baseline_w = sum(r[2] for r in baseline) / len(baseline)

    print(f"Baseline {baseline_w:.2f} W. Running: {' '.join(cmd)}\n")
    stop = threading.Event()
    sampler = threading.Thread(target=sample, args=(None, args.period, "run", rows, stop))
    sampler.start()
    t0 = time.monotonic()
    result = subprocess.run(cmd)
    run_s = time.monotonic() - t0
    stop.set()
    sampler.join()

    run = [r for r in rows if r[1] == "run"]
    avg_w = sum(r[2] for r in run) / len(run)
    peak_w = max(r[2] for r in run)
    extra_j = energy_j(run, baseline_w)

    out_dir = Path(__file__).resolve().parent / "power_logs"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{args.label}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with out_file.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s", "phase", "pi_rails_w"])
        start = rows[0][0]
        w.writerows((f"{t - start:.3f}", phase, f"{p:.3f}") for t, phase, p in rows)

    print("\n--- Pi rail power (excludes AI HAT) ---")
    print(f"Label:            {args.label}")
    print(f"Baseline:         {baseline_w:.2f} W")
    print(f"During run:       {avg_w:.2f} W average, {peak_w:.2f} W peak")
    print(f"Run time:         {run_s:.1f} s")
    print(f"Extra energy:     {extra_j:.1f} J  (above baseline)")
    print(f"Samples saved to: {out_file}")
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
