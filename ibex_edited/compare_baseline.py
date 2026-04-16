#!/usr/bin/env python3
"""Compare optimized icache proxy results against the baseline."""

import json, sys, os

BASELINE = os.path.join(os.path.dirname(__file__), "..", "results", "test-baseline", "icache_proxy_coremark.json")
OPTIMIZED = os.path.join(os.path.dirname(__file__), "icache_proxy_coremark.json")

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

def compare(policy, base, opt):
    b = base[policy]
    o = opt[policy]
    print(f"\n{'='*72}")
    print(f"  {policy.upper()} Policy Comparison — Baseline vs Optimized (FB_THRESHOLD)")
    print(f"{'='*72}")

    print(f"\n  {'Metric':<28} {'Baseline':>14} {'Optimized':>14} {'Δ':>10} {'Change':>10}")
    print(f"  {'-'*28} {'-'*14} {'-'*14} {'-'*10} {'-'*10}")

    # Counters
    for key in ["cycles", "instret", "fetch_wait",
                "tag_reads", "data_reads", "tag_writes", "data_writes",
                "evictions", "inval_tag_writes"]:
        bv = b["counters"][key]
        ov = o["counters"][key]
        delta = ov - bv
        print(f"  {key:<28} {fmt(bv):>14} {fmt(ov):>14} {delta:>+10,} {pct(bv, ov):>10}")

    # Metrics
    print()
    for key in ["proxy_energy", "proxy_energy_per_inst", "proxy_energy_per_cycle"]:
        bv = b["metrics"][key]
        ov = o["metrics"][key]
        delta = ov - bv
        print(f"  {key:<28} {fmt(bv):>14} {fmt(ov):>14} {delta:>+10,.1f} {pct(bv, ov):>10}")

    print()
    energy_saved = b["metrics"]["proxy_energy"] - o["metrics"]["proxy_energy"]
    reads_saved = b["counters"]["tag_reads"] - o["counters"]["tag_reads"]
    print(f"  *** SRAM reads eliminated:  {reads_saved:,}")
    print(f"  *** Proxy energy saved:     {energy_saved:,.0f}  ({pct(b['metrics']['proxy_energy'], o['metrics']['proxy_energy'])})")

def main():
    if not os.path.exists(BASELINE):
        print(f"ERROR: baseline not found at {BASELINE}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(OPTIMIZED):
        print(f"ERROR: optimized results not found at {OPTIMIZED}", file=sys.stderr)
        sys.exit(1)

    base = load(BASELINE)
    opt = load(OPTIMIZED)

    print("Baseline:  ", os.path.abspath(BASELINE))
    print("Optimized: ", os.path.abspath(OPTIMIZED))

    compare("rr", base, opt)
    compare("plru", base, opt)

    print(f"\n{'='*72}")
    print("  SUMMARY")
    print(f"{'='*72}")
    print(f"  Change: FB_THRESHOLD = NUM_FB - 2  →  NUM_FB - 3  (2 → 1)")
    print(f"  Effect: Throttle speculative prefetch when ≥2 fill buffers active")
    print()
    for p in ["rr", "plru"]:
        be = base[p]["metrics"]["proxy_energy"]
        oe = opt[p]["metrics"]["proxy_energy"]
        print(f"  {p.upper():>4}:  {be:>12,.0f}  →  {oe:>12,.0f}   ({pct(be, oe)})")
    print()

if __name__ == "__main__":
    main()
