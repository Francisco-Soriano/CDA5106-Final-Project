---
name: ICache RAM Read Gating
overview: Replace lookup_req_ic0 with lookup_actual_ic0 in the tag_req_ic0 and data_req_ic0 assignments to eliminate wasted RAM reads when the IC1 result would be discarded anyway (cache disabled or invalidation in progress). Two-line change in rtl/ibex_icache.sv only.
todos:
  - id: gate-tag-req
    content: Replace lookup_req_ic0 with lookup_actual_ic0 in tag_req_ic0 assign in rtl/ibex_icache.sv
    status: pending
  - id: gate-data-req
    content: Replace lookup_req_ic0 with lookup_actual_ic0 in data_req_ic0 assign in rtl/ibex_icache.sv
    status: pending
  - id: ram-gate-lint
    content: Run Verilator lint on ibex_top_tracing with maxperf-pmp-bmfull-icache config to verify no errors
    status: pending
  - id: ram-gate-measure
    content: Run CoreMark co-sim before and after, confirm perf_ic_tag_read_o and perf_ic_data_read_o decrease, all others unchanged
    status: pending
isProject: false
---

# ICache Tag and Data RAM Read Gating

## Background

The only file that changes is [`rtl/ibex_icache.sv`](rtl/ibex_icache.sv).

## Root Cause

`tag_req_ic0` and `data_req_ic0` currently fire on every `lookup_req_ic0`, regardless of whether the IC1 result will actually be used:

```systemverilog
assign tag_req_ic0  = lookup_req_ic0 | fill_req_ic0 | inval_write_req | ecc_write_req;
assign data_req_ic0 = lookup_req_ic0 | fill_req_ic0;
```

The IC1 pipeline result is only consumed when `lookup_valid_ic1 = 1`, which is registered from `lookup_actual_ic0`:

```systemverilog
assign lookup_actual_ic0 = lookup_grant_ic0 & icache_enable_i & ~inval_block_cache;
```

When `lookup_actual_ic0 = 0` — during `icache_enable_i = 0` (cache runtime-disabled) or `inval_block_cache = 1` (256-cycle invalidation sweep at startup and after `icache_inval_i`) — all tag and data RAM read outputs feed into `tag_match_ic1`, `tag_hit_ic1`, `tag_invalid_ic1`, and `hit_data_ecc_ic1`, all of which are qualified by `lookup_valid_ic1 = 0`. Every one of those reads is wasted.

`lookup_grant_ic0` is NOT changed, so instruction fetch (bus address generation via `prefetch_addr_q → lookup_addr_ic0`, fill buffer allocation, `instr_req_o`) is completely unaffected.

## The Change — 2 Lines Only

Old:
```systemverilog
assign tag_req_ic0  = lookup_req_ic0 | fill_req_ic0 | inval_write_req | ecc_write_req;
assign data_req_ic0 = lookup_req_ic0 | fill_req_ic0;
```

New:
```systemverilog
assign tag_req_ic0  = lookup_actual_ic0 | fill_req_ic0 | inval_write_req | ecc_write_req;
assign data_req_ic0 = lookup_actual_ic0 | fill_req_ic0;
```

`inval_write_req` and `ecc_write_req` paths in `tag_req_ic0` are unchanged — those tag writes still happen correctly. `fill_req_ic0` in both assigns is unchanged — cache fill writes and reads are unaffected.

## Correctness Notes

- `inval_block_cache = 1` → `lookup_actual_ic0 = 0` → tag and data lookup reads suppressed. Tag invalidation writes still fire via `inval_write_req`. No functional change to invalidation sweep.
- `icache_enable_i = 0` → `lookup_actual_ic0 = 0` → RAM reads suppressed. Bus fetches still happen via `lookup_grant_ic0 = lookup_req_ic0` (unchanged). Sequential address advancement via `prefetch_addr_q` still works.
- ECC write path: `ecc_write_req = 1` → `lookup_req_ic0 = 0` (already gated in its own assign), so `lookup_actual_ic0 = 0` anyway. No change in behavior.
- Fill commit: `fill_grant_ic0 = 1` only when `lookup_req_ic0 = 0` → `lookup_actual_ic0 = 0` → `tag_req_ic0 = 0 | 1 | 0 | 0 = 1`. Fill tag write still fires correctly via `fill_req_ic0`. ✓

**Known edge case (pre-existing, not introduced by this change):** When `icache_enable_i = 0` AND a fill buffer is pending but `fill_grant_ic0 = 0` (blocked because `lookup_req_ic0 = 1` has priority), `fill_req_ic0 = 1` still drives `tag_req_ic0 = 1`. The tag RAM is read at `lookup_index_ic0` with no useful result. This is a pre-existing behavior that our optimization cannot eliminate without restructuring the arbitration logic. It occurs only in a rare transient state (fill pending + lookup active + cache disabled simultaneously) and does not affect correctness or significantly limit the counter reduction.

## Counter Effects

| Counter | Effect | Condition |
|---|---|---|
| `perf_ic_tag_read_o` | Decreases | During invalidation (256 cycles/event) and while `icache_enable_i = 0` |
| `perf_ic_data_read_o` | Decreases | Same |
| `perf_ic_tag_write_o` | No change | Fill/inval/ECC write paths unchanged |
| `perf_ic_data_write_o` | No change | Fill write path unchanged |
| `perf_ic_evict_o` | No change | Replacement policy unchanged |
| `perf_ic_inval_tag_write_o` | No change | `inval_write_req` unchanged |

## Research Context — Full Counter Coverage

Combined with the other optimizations, every counter is now moved by at least one change:

| Counter | Optimization |
|---|---|
| `perf_ic_tag_read_o` | **This optimization** |
| `perf_ic_data_read_o` | **This optimization** + Way-Prediction (Opt 1) |
| `perf_ic_tag_write_o` | PLRU (Opt 4) |
| `perf_ic_data_write_o` | PLRU (Opt 4) |
| `perf_ic_evict_o` | PLRU (Opt 4) |
| `perf_ic_inval_tag_write_o` | Unchanged — serves as baseline reference |

## Verification

Run lint first:
```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache fusesoc_opts)
fusesoc --cores-root . run --target=lint --tool=verilator lowrisc:ibex:ibex_top_tracing $IBEX_CONFIG_OPTS
```

Then run CoreMark before and after:
```bash
./ci/run-cosim-test.sh --skip-pass-check CoreMark \
    examples/sw/benchmarks/coremark/coremark.elf
cat ibex_simple_system_pcount.csv
```

Watch `perf_ic_tag_read_o` and `perf_ic_data_read_o` decrease. All other counters should match baseline.
