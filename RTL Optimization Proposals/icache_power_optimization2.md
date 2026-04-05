---
name: ICache Power Optimization 2 — Reduce Fill Buffer Count
overview: "Reduce NUM_FB from 4 to 2 in ibex_icache.sv to halve fill buffer register toggling and cut dynamic power. This is a single one-line change at line 71."
todos:
  - id: reduce-num-fb
    content: Change localparam int unsigned NUM_FB = 4 to NUM_FB = 2 at line 71 of rtl/ibex_icache.sv
    status: pending
  - id: lint-verify
    content: Run Verilator lint on ibex_top_tracing with maxperf-pmp-bmfull-icache config to verify no syntax/type errors
    status: pending
  - id: measure
    content: Run CoreMark co-sim before and after the change, compare ibex_simple_system_pcount.csv Cycles and Fetch Wait counters
    status: pending
isProject: false
---

# ICache Power Optimization 2 — Reduce NUM_FB from 4 to 2

Single change to `rtl/ibex_icache.sv`. Self-contained and independent of any other optimizations.

---

## Optimization 2: Reduce NUM_FB from 4 to 2

**Root cause:** All four fill buffer state machines are always clock-enabled via `fill_entry_en[fb] = fill_alloc[fb] | fill_busy_q[fb]`. Buffers 2 and 3 toggle their ~12 state registers (see lines 747–772) every time they are allocated, even if only 1–2 outstanding misses are typical.

**Change:** Line 71 only.

Old:

```systemverilog
localparam int unsigned NUM_FB = 4;
```

New:

```systemverilog
localparam int unsigned NUM_FB = 2;   // reduced for power; minimum allowed is 2
```

`FB_THRESHOLD = NUM_FB - 2` (line 73) automatically becomes `0`, meaning `lookup_throttle = (fb_fill_level > 0)` — throttling engages the moment any non-stale fill buffer is busy. This is more conservative than the 4-buffer case (throttle threshold was 2) but is functionally correct — the comment at line 70 only states "must be >= 2".

**Why the 1-bit `fb_fill_level` is safe with NUM_FB=2:**
`fb_fill_level` is `[$clog2(NUM_FB)-1:0]` wide (line 119). With NUM_FB=2, that is 1 bit — representable values are 0 and 1. The concern is whether the counter can reach 2 (both buffers busy, non-stale). It cannot: when `fb_fill_level = 1` (one non-stale busy buffer), `lookup_throttle = 1`, which gates `lookup_req_ic0 = 0`, which prevents `fill_new_alloc = lookup_grant_ic0 = 0`. No new fill buffer can be allocated until the busy one completes. The count never overflows.

**Impact:**

- ~50% fewer fill buffer state registers (`fill_busy_q`, `fill_older_q`, `fill_stale_q`, `fill_cache_q`, `fill_hit_q`, `fill_ext_cnt_q`, `fill_ext_done_q`, `fill_rvd_cnt_q`, `fill_ram_done_q`, `fill_out_cnt_q`, `fill_err_q`, `fill_addr_q`, `fill_way_q`, `fill_data_q` — all `[NUM_FB-1:0]` or `[NUM_FB]` indexed) are cut in half
- `fill_older_q` drops from 4×4 to 2×2 (12 fewer bits)
- `fb_fill_level` drops from 2-bit to 1-bit counter
- **Risk:** under workloads with 3–4 outstanding cache misses (uncommon for sequential instruction fetch), throughput can drop since throttling is more aggressive

---

## Summary of Change

- `localparam int unsigned NUM_FB = 4;` → `2` (line 71) — the only change for this optimization

---

## Verification

Lint + CoreMark measurement flow:

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache fusesoc_opts)
fusesoc --cores-root . run --target=lint --tool=verilator lowrisc:ibex:ibex_top_tracing $IBEX_CONFIG_OPTS
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
cat ibex_simple_system_pcount.csv
```
