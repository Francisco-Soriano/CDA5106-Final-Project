#!/usr/bin/env python3
# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
from pathlib import Path


DEFAULT_WEIGHTS = {
    "tag_reads": 1.0,
    "data_reads": 2.0,
    "tag_writes": 2.0,
    "data_writes": 3.0,
    "evictions": 1.0,
    "inval_tag_writes": 1.0,
}

COUNTER_NAMES = {
    "cycles": "Cycles",
    "instret": "Instructions Retired",
    "fetch_wait": "Fetch Wait",
    "tag_reads": "I$ Tag Array Reads",
    "data_reads": "I$ Data Array Reads",
    "tag_writes": "I$ Tag Array Writes",
    "data_writes": "I$ Data Array Writes",
    "evictions": "I$ Evictions",
    "inval_tag_writes": "I$ Invalidation Tag Writes",
}

REQUIRED_COUNTER_KEYS = {"cycles", "instret", "fetch_wait", "tag_reads", "data_reads", "tag_writes"}


def parse_args():
    parser = argparse.ArgumentParser(description="Compute I$ proxy energy from pcount CSVs.")
    parser.add_argument("--rr", required=True, help="RR pcount CSV path")
    parser.add_argument("--plru", required=True, help="PLRU pcount CSV path")
    parser.add_argument("--out-json", required=True, help="Output JSON path")
    parser.add_argument("--w-tr", type=float, default=DEFAULT_WEIGHTS["tag_reads"])
    parser.add_argument("--w-dr", type=float, default=DEFAULT_WEIGHTS["data_reads"])
    parser.add_argument("--w-tw", type=float, default=DEFAULT_WEIGHTS["tag_writes"])
    parser.add_argument("--w-dw", type=float, default=DEFAULT_WEIGHTS["data_writes"])
    parser.add_argument("--w-ev", type=float, default=DEFAULT_WEIGHTS["evictions"])
    parser.add_argument("--w-inv", type=float, default=DEFAULT_WEIGHTS["inval_tag_writes"])
    return parser.parse_args()


def read_csv(path: Path):
    with path.open("r", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV is empty: {path}")

    values = {}
    for row in rows:
        if len(row) < 2:
            continue
        name = row[0].strip()
        value = row[1].strip()
        if not name:
            continue
        try:
            values[name] = int(value)
        except ValueError as err:
            raise ValueError(f"Failed to parse value '{value}' for '{name}' in {path}") from err
    return values


def require_counter(values, key, path):
    name = COUNTER_NAMES[key]
    if name not in values:
        raise KeyError(f"Missing counter '{name}' in {path}")
    return values[name]


def get_counter(values, key, path):
    name = COUNTER_NAMES[key]
    if name in values:
        return values[name]
    if key in REQUIRED_COUNTER_KEYS:
        raise KeyError(f"Missing counter '{name}' in {path}")
    return 0


def safe_div(num, den):
    return 0.0 if den == 0 else float(num) / float(den)


def summarize(values, path: Path, weights):
    counters = {k: get_counter(values, k, path) for k in COUNTER_NAMES.keys()}

    energy = (
        weights["tag_reads"] * counters["tag_reads"]
        + weights["data_reads"] * counters["data_reads"]
        + weights["tag_writes"] * counters["tag_writes"]
        + weights["data_writes"] * counters["data_writes"]
        + weights["evictions"] * counters["evictions"]
        + weights["inval_tag_writes"] * counters["inval_tag_writes"]
    )

    return {
        "file": str(path),
        "counters": counters,
        "metrics": {
            "proxy_energy": energy,
            "proxy_energy_per_inst": safe_div(energy, counters["instret"]),
            "proxy_energy_per_cycle": safe_div(energy, counters["cycles"]),
        },
    }


def print_diff(rr, plru):
    rr_m = rr["metrics"]
    plru_m = plru["metrics"]
    rr_c = rr["counters"]
    plru_c = plru["counters"]

    def d(metric):
        return plru_m[metric] - rr_m[metric]

    print("RR vs PLRU (PLRU - RR)")
    print(f"Cycles: {plru_c['cycles']} - {rr_c['cycles']} = {plru_c['cycles'] - rr_c['cycles']}")
    print(f"InstRet: {plru_c['instret']} - {rr_c['instret']} = {plru_c['instret'] - rr_c['instret']}")
    print(
        f"Fetch Wait: {plru_c['fetch_wait']} - {rr_c['fetch_wait']} = "
        f"{plru_c['fetch_wait'] - rr_c['fetch_wait']}"
    )
    print(f"E: {plru_m['proxy_energy']:.3f} - {rr_m['proxy_energy']:.3f} = {d('proxy_energy'):.3f}")
    print(
        f"E/inst: {plru_m['proxy_energy_per_inst']:.9f} - {rr_m['proxy_energy_per_inst']:.9f} = "
        f"{d('proxy_energy_per_inst'):.9f}"
    )
    print(
        f"E/cycle: {plru_m['proxy_energy_per_cycle']:.9f} - {rr_m['proxy_energy_per_cycle']:.9f} = "
        f"{d('proxy_energy_per_cycle'):.9f}"
    )


def main():
    args = parse_args()
    rr_path = Path(args.rr)
    plru_path = Path(args.plru)
    out_json = Path(args.out_json)

    weights = {
        "tag_reads": args.w_tr,
        "data_reads": args.w_dr,
        "tag_writes": args.w_tw,
        "data_writes": args.w_dw,
        "evictions": args.w_ev,
        "inval_tag_writes": args.w_inv,
    }

    rr = summarize(read_csv(rr_path), rr_path, weights)
    plru = summarize(read_csv(plru_path), plru_path, weights)

    report = {"weights": weights, "rr": rr, "plru": plru}
    out_json.write_text(json.dumps(report, indent=2) + "\n")

    print_diff(rr, plru)


if __name__ == "__main__":
    main()
