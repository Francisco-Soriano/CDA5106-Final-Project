#!/usr/bin/env python3
"""Compare icache proxy-energy results across all optimization variants.

Loads results/<variant>/icache_proxy_coremark.json for each variant and prints
a comparison table showing absolute values, deltas from baseline, and
percentage change.  Exits with status 1 if any expected result file is missing.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")

VARIANTS = [
    ("baseline",          "Baseline (stock icache)"),
    ("opt1-linebuffer",   "Opt 1: Same-line line buffer"),
    ("opt2-fillbuffer",   "Opt 2: Sequential line buffer + FB suppression"),
    ("opt3-combined",     "Opt 3: Combined (LB + FB supp. + throttle)"),
    ("opt4-fb-threshold", "Opt 4: Aggressive FB_THRESHOLD (NUM_FB-3)"),
]

COUNTER_KEYS = [
    "cycles", "instret", "fetch_wait",
    "tag_reads", "data_reads", "tag_writes", "data_writes",
    "evictions", "inval_tag_writes",
]

METRIC_KEYS = [
    "proxy_energy", "proxy_energy_per_inst", "proxy_energy_per_cycle",
]


def load(path):
    with open(path) as f:
        return json.load(f)


def pct(old, new):
    if old == 0:
        return "N/A"
    return f"{(new - old) / old * 100:+.2f}%"


def fmt(v):
    if isinstance(v, float):
        return f"{v:,.4f}"
    return f"{v:,}"


def print_policy_table(policy, results, variants):
    """Print a per-policy comparison table across all variants."""
    base = results["baseline"][policy]

    print(f"\n{'=' * 100}")
    print(f"  {policy.upper()} Policy — All Variants vs Baseline")
    print(f"{'=' * 100}")

    hdr = f"  {'Metric':<28}"
    for tag, _ in variants:
        hdr += f" {tag:>14}"
    print(hdr)
    print(f"  {'-' * 28}" + f" {'-' * 14}" * len(variants))

    for key in COUNTER_KEYS:
        row = f"  {key:<28}"
        for tag, _ in variants:
            val = results[tag][policy]["counters"][key]
            row += f" {fmt(val):>14}"
        print(row)

        row_delta = f"    {'Δ ' + key:<26}"
        for tag, _ in variants:
            if tag == "baseline":
                row_delta += f" {'—':>14}"
            else:
                bv = base["counters"][key]
                ov = results[tag][policy]["counters"][key]
                row_delta += f" {pct(bv, ov):>14}"
        print(row_delta)

    print()

    for key in METRIC_KEYS:
        row = f"  {key:<28}"
        for tag, _ in variants:
            val = results[tag][policy]["metrics"][key]
            row += f" {fmt(val):>14}"
        print(row)

        row_delta = f"    {'Δ ' + key:<26}"
        for tag, _ in variants:
            if tag == "baseline":
                row_delta += f" {'—':>14}"
            else:
                bv = base["metrics"][key]
                ov = results[tag][policy]["metrics"][key]
                row_delta += f" {pct(bv, ov):>14}"
        print(row_delta)

    print()


def print_summary(results, variants):
    """Print a compact energy summary with pass/fail."""
    print(f"\n{'=' * 100}")
    print(f"  SUMMARY — Proxy Energy (lower is better)")
    print(f"{'=' * 100}")

    header = f"  {'Variant':<40} {'RR Energy':>14} {'Δ RR':>10} {'PLRU Energy':>14} {'Δ PLRU':>10} {'Status':>8}"
    print(header)
    print(f"  {'-' * 40} {'-' * 14} {'-' * 10} {'-' * 14} {'-' * 10} {'-' * 8}")

    base_rr = results["baseline"]["rr"]["metrics"]["proxy_energy"]
    base_plru = results["baseline"]["plru"]["metrics"]["proxy_energy"]

    for tag, desc in variants:
        rr_e = results[tag]["rr"]["metrics"]["proxy_energy"]
        plru_e = results[tag]["plru"]["metrics"]["proxy_energy"]

        if tag == "baseline":
            delta_rr = "—"
            delta_plru = "—"
            status = "BASE"
        else:
            delta_rr = pct(base_rr, rr_e)
            delta_plru = pct(base_plru, plru_e)
            improved = (rr_e <= base_rr) and (plru_e <= base_plru)
            status = "PASS" if improved else "REGR"

        print(f"  {desc:<40} {rr_e:>14,.0f} {delta_rr:>10} {plru_e:>14,.0f} {delta_plru:>10} {status:>8}")

    print()


def main():
    results = {}
    missing = []

    for tag, desc in VARIANTS:
        path = os.path.join(RESULTS_DIR, tag, "icache_proxy_coremark.json")
        if not os.path.exists(path):
            # Try legacy naming (test-<tag>)
            path = os.path.join(RESULTS_DIR, f"test-{tag}", "icache_proxy_coremark.json")
        if os.path.exists(path):
            results[tag] = load(path)
        else:
            missing.append(tag)

    if missing:
        print(f"WARNING: Missing results for: {', '.join(missing)}", file=sys.stderr)
        print(f"  Run ./run_all.sh to generate them, or run with --available-only.\n",
              file=sys.stderr)

    available = [tag for tag, _ in VARIANTS if tag in results]

    if "baseline" not in results:
        print("ERROR: Baseline results are required.", file=sys.stderr)
        sys.exit(1)

    if len(available) < 2:
        print("ERROR: Need at least baseline + one variant.", file=sys.stderr)
        sys.exit(1)

    filtered = [(t, d) for t, d in VARIANTS if t in results]

    print(f"Results directory: {RESULTS_DIR}")
    print(f"Variants loaded:  {', '.join(available)}")

    for policy in ["rr", "plru"]:
        print_policy_table(policy, results, filtered)

    print_summary(results, filtered)


if __name__ == "__main__":
    main()
