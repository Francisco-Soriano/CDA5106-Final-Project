---
name: ICache Power Optimizations — Extended Plan
overview: "Extend the ibex_icache.sv power optimization plan with two additional changes: reduce NUM_FB from 4 to 2 to halve fill buffer register toggling, and apply a corrected gate to the prefetch address enable signal."
todos:
  - id: add-signals
    content: Add way-prediction signal declarations to rtl/ibex_icache.sv after existing logic declarations (~line 200)
    status: pending
  - id: register-index
    content: No action — lookup_index_ic1 is already a top-level global signal registered in both pipeline blocks in this version of the RTL
    status: cancelled
  - id: add-prediction-logic
    content: Add predicted_way_ic0, predicted_way_ic1_q pipeline register, way_mispredict_ic1 detection, tag_hit_ic1_masked, and way_hint update flop before IC0 data RAM section (~line 270)
    status: pending
  - id: replace-banks
    content: Replace data_banks_ic0 = tag_banks_ic0 with predicted-way one-hot select, preserving fill_grant_ic0 and ecc_write_req cases (~line 275)
    status: pending
  - id: mask-hit-downstream
    content: Replace tag_hit_ic1 with tag_hit_ic1_masked in fill_hit_ic1 (~line 614) and ecc_err_ic1 (~line 451)
    status: pending
  - id: reduce-num-fb
    content: Change localparam int unsigned NUM_FB = 4 to NUM_FB = 2 at line 71 of rtl/ibex_icache.sv
    status: pending
  - id: lint-verify
    content: Run Verilator lint on ibex_top_tracing with maxperf-pmp-bmfull-icache config to verify no syntax/type errors
    status: pending
  - id: measure
    content: Run CoreMark co-sim before and after all changes, compare ibex_simple_system_pcount.csv Cycles and Fetch Wait counters
    status: pending
isProject: false
---

# ICache Power Optimizations — Extended Plan

Three independent optimizations to `[rtl/ibex_icache.sv](rtl/ibex_icache.sv)`. All changes are self-contained in that one file.

---

## Optimization 1: Way-Prediction for Data RAM (existing plan)

Already fully specified in `icache_way-prediction_optimization1.md`. **Key update:** `lookup_index_ic1_q` is NOT a new signal — `lookup_index_ic1` is already a top-level global signal in this version of the RTL. Step 2 of that plan is cancelled. All references to `lookup_index_ic1_q` in the hint update use `lookup_index_ic1` instead.

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

- ~50% fewer fill buffer state registers (`fill_busy_q`, `fill_older_q`, `fill_stale_q`, `fill_cache_q`, `fill_hit_q`, `fill_evict_q`, `fill_ext_cnt_q`, `fill_ext_done_q`, `fill_rvd_cnt_q`, `fill_ram_done_q`, `fill_out_cnt_q`, `fill_err_q`, `fill_addr_q`, `fill_way_q`, `fill_data_q` — all `[NUM_FB-1:0]` or `[NUM_FB]` indexed) are cut in half
- `fill_older_q` drops from 4×4 to 2×2 (12 fewer bits)
- `fb_fill_level` drops from 2-bit to 1-bit counter
- **Risk:** under workloads with 3–4 outstanding cache misses (uncommon for sequential instruction fetch), throughput can drop since throttling is more aggressive

---

## Optimization 3: Gate Prefetch Address on Cache Enable — Not Applicable

**Claimed root cause:** `prefetch_addr_en = branch_i | lookup_grant_ic0` (line 217) toggles `prefetch_addr_q` every cycle a lookup is granted.

**Why no RTL change is safe:**

When `icache_enable_i = 0` (direct bus fetch mode), `instr_addr_o` is driven from `lookup_addr_ic0 = prefetch_addr_q` (line 244). The prefetch address must advance on every granted lookup to generate the correct sequential bus addresses — gating the update with `icache_enable_i` would stall the address at the same value and repeatedly re-request the same instruction word.

When `icache_enable_i = 1` (normal cached mode), the sequential prefetch advance is the entire purpose of `prefetch_addr_q` — it must toggle.

There is therefore no legal RTL gate for this register in either mode. Synthesis clock-gating (`if (enable)` inside `always_ff`) handles the physical ICG cell automatically — no source-level change is needed or safe. **No RTL change is proposed.**

---

## Summary of Changes

- `localparam int unsigned NUM_FB = 4;` → `2` (line 71) — the only change for Optimization 2
- All Optimization 1 changes remain as specified in the existing plan
- No changes for Optimization 3 (RTL is already correct; synthesis handles clock gating)

## Verification

Same lint + CoreMark measurement flow as Optimization 1:

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache fusesoc_opts)
fusesoc --cores-root . run --target=lint --tool=verilator lowrisc:ibex:ibex_top_tracing $IBEX_CONFIG_OPTS
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
cat ibex_simple_system_pcount.csv
```

