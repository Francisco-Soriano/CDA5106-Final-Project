# Planner Agent: I$ Power & Performance (CoreMark baseline)

**Role:** Principal Power & Performance Architect  
**Scope:** `ibex_icache.sv` only for RTL changes.  
**Success metric:** Proxy energy from `util/icache_proxy_energy.py` (Tag/Data array read/write counters from `ibex_simple_system_pcount.csv`).

**Baseline source:** `ibex_edited/icache_proxy_coremark.json`

---

## Baseline proxy energy (RR, total 6,009,210)

Using the weights in `icache_proxy_coremark.json` and the RR counters:

| Component     | Calculation           | Contribution        |
|---------------|-----------------------|---------------------|
| **Data reads** | 2.0 × 1,937,660      | **3,875,320 (~64.5%)** |
| **Tag reads**  | 1.0 × 1,937,660      | **1,937,660 (~32.2%)** |
| **Data writes**| 3.0 × 39,246         | 117,738 (~2.0%)     |
| **Tag writes** | 2.0 × 39,246         | 78,492 (~1.3%)      |

`tag_reads` and `data_reads` are **equal** because every lookup drives tag and data RAMs together in IC0. **Reads dominate (~97% of proxy energy);** writes are minor for CoreMark.

PLRU vs RR only nudges proxy (~0.28% lower energy in the JSON) mostly via fewer fills/writes, not reads.

---

## Where the RTL spends those reads

Lookups assert both tag and data access in parallel; all ways are enabled for normal lookups (`ibex_icache.sv`):

- `tag_req_ic0`, `tag_banks_ic0` (all ways on lookup)
- `data_req_ic0`, `data_banks_ic0` (tied to tag banks except ECC path)

Perf pulses track those combined read events—so **fewer lookup cycles that actually touch RAM** lowers both `I$ Tag Array Reads` and `I$ Data Array Reads`:

```systemverilog
assign perf_ic_tag_read_o  = tag_req_ic0 & ~tag_write_ic0;
assign perf_ic_data_read_o = data_req_ic0 & ~data_write_ic0;
```

---

## Recommended single-iteration optimization

**Same-line line buffer (last-line register) to skip redundant tag+data RAM reads.**

Sequential fetches often stay inside one cache line. Today, every granted lookup still opens tag and data arrays for the next address, even when that address is still in the line already read. Holding the last line’s tag/index and full line data in flops and comparing the current lookup’s line address lets you **suppress `tag_req_ic0` / `data_req_ic0` for that lookup** while still advancing the front-end / fill-bookkeeping as required.

### Signals / areas to touch in `ibex_icache.sv`

| Area              | Signals / constructs |
|-------------------|----------------------|
| New state         | e.g. `line_buf_valid_q`, register of line tag bits + index (or full line compare field), full line data (ECC-wide if `ICacheECC`), optional error bits |
| Compare (IC0)     | e.g. `line_buf_hit_ic0` from buffered tag/index vs current `lookup_addr_ic0` |
| Gate RAM reads    | `tag_req_ic0`, `data_req_ic0`: for **lookups** only, do not assert when `line_buf_hit_ic0` (still allow fill / inval / ECC paths) |
| Lookup / prefetch | `lookup_req_ic0` / `lookup_grant_ic0` / `prefetch_addr_en`: ensure prefetch and fill allocation still advance correctly when SRAM is skipped |
| Fill buffer / output | `line_data` mux region: feed hit data from the line buffer when the outstanding access was a buffer hit |
| Update buffer     | When `lookup_valid_ic1 && tag_hit_ic1`, latch hit line data and address tag/index into the buffer |
| Invalidate        | Clear `line_buf_valid_q` on `branch_i`, `~icache_enable_i`, `icache_inval_i`, and when a fill could overwrite that line; if **scrambling** is used, invalidate conservatively on key / inval FSM events that imply stale decrypted data |

**Expected effect:** Large reduction in both tag and data read counters on sequential code (e.g. CoreMark), targeting the dominant weighted term (data reads).

---

## Clarifications before locking microarchitecture

1. **Build parameters:** Actual values of `ICacheECC`, `ICachePLRU`, and `BranchCache` for the CoreMark run.
2. **Scrambling:** Whether `ic_scr_key_valid_i` / scrambling is active in the simple system; if yes, line-buffer invalidation must be conservative on key changes and cache inval.
3. **Metric alignment:** Confirm the line buffer reduces `perf_ic_*` only when RAM `req` is truly deasserted so proxy tracks intended activity.

---

## Related plan

Broader multi-option roadmap: `icache_power_optimization_plan_19304045.plan.md`.
