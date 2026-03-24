# I$ Proxy-Power Implementation Report

## Scope Completed

Implemented the full RR vs PLRU proxy-power plan from `doc/projectplan.md`:

- Added replacement-policy control (RR baseline, optional PLRU) for I$.
- Added I$ event counters and plumbed them into mhpmcounters and pcount CSV export.
- Added RR/PLRU proxy configs for controlled A/B runs.
- Added proxy-energy analysis script.
- Updated run documentation for RR/PLRU comparison flow.

---

## 1) Config Surface and New Experiment Configs

### Updated file

- `ibex_configs.yaml`

### Changes

- Added new configuration key `ICachePLRU` to all existing config entries, defaulting to `0`.
- Added two new experiment configs:
  - `maxperf-pmp-bmfull-icache-rr-proxy`
  - `maxperf-pmp-bmfull-icache-plru-proxy`
- Set in those new configs:
  - `ICache=1`
  - `ICacheECC=1`
  - `ICachePLRU=0` (RR config) or `1` (PLRU config)
  - `MHPMCounterNum=16` (ensures indices 13..18 exist)

### Parser support

- Updated `util/ibex_config.py`:
  - Added `ICachePLRU` to known fields.
  - Added `self.icache_plru` parsing.

This fixes unknown-key failures when using `util/ibex_config.py` with the new key.

---

## 2) Replacement Policy Implementation (RR + PLRU)

### Updated file

- `rtl/ibex_icache.sv`

### Changes

- Added new parameter:
  - `ICachePLRU`
- Added PLRU state and selection logic for 2-way cache:
  - Per-set MRU tracking bit (`plru_mru_way_q`).
  - PLRU victim is opposite of MRU.
  - Victim select chooses:
    - first invalid way if any invalid exists (invalid-first preserved),
    - else RR or PLRU based on `ICachePLRU`.
- Kept existing RR behavior as baseline when `ICachePLRU=0`.

### Correctness intent

- Invalid-first allocation remains unchanged.
- Eviction behavior only applies when allocating into full sets.
- Added assertion:
  - `icache_plru_2way_only` requiring 2-way operation.

---

## 3) Event Pulses Added at I$ Source

### Updated file

- `rtl/ibex_icache.sv`

### New perf outputs

- `perf_ic_tag_read_o`
- `perf_ic_data_read_o`
- `perf_ic_tag_write_o`
- `perf_ic_data_write_o`
- `perf_ic_evict_o`
- `perf_ic_inval_tag_write_o`

### Event definitions implemented

- Tag read pulse: tag request and not tag write.
- Data read pulse: data request and not data write.
- Tag write pulse: tag write asserted.
- Data write pulse: data write asserted.
- Invalidation tag write pulse: invalidation write request.
- Eviction pulse: fill allocation commit writes into cache and victim was valid.

Eviction logic was implemented by tracking whether the chosen way came from full-set replacement (no invalid way) at fill-way capture time, then pulsing on fill RAM arbitration commit.

---

## 4) Counter Plumbing (IF -> Core -> CSRs)

### Updated files

- `rtl/ibex_if_stage.sv`
- `rtl/ibex_core.sv`
- `rtl/ibex_cs_registers.sv`

### Changes

- Added `ICachePLRU` parameter plumbing from IF stage instantiation down to `ibex_icache`.
- Added perf signal outputs in IF stage and tie-offs in non-ICache path.
- Added perf signal wiring in `ibex_core` from IF stage to CSR block.
- Extended CSR perf inputs and `mhpmcounter_incr` map in `ibex_cs_registers.sv`:
  - 13: I$ Tag Array Reads
  - 14: I$ Data Array Reads
  - 15: I$ Tag Array Writes
  - 16: I$ Data Array Writes
  - 17: I$ Evictions
  - 18: I$ Invalidation Tag Writes

---

## 5) pcount CSV Export Names

### Updated file

- `dv/verilator/pcount/cpp/ibex_pcounts.cc`

### Changes

Extended `ibex_counter_names` with:

- `I$ Tag Array Reads`
- `I$ Data Array Reads`
- `I$ Tag Array Writes`
- `I$ Data Array Writes`
- `I$ Evictions`
- `I$ Invalidation Tag Writes`

These names align with CSR counter indices 13..18.

---

## 6) Analysis Tool Added

### Added file

- `util/icache_proxy_energy.py`

### Capabilities

- Reads RR and PLRU pcount CSV files.
- Validates required counters are present.
- Computes:
  - `proxy_energy`
  - `proxy_energy_per_inst`
  - `proxy_energy_per_cycle`
- Uses default weights:
  - `w_tr=1`, `w_dr=2`, `w_tw=2`, `w_dw=3`, `w_ev=1`, `w_inv=1`
- Supports weight overrides via CLI.
- Writes JSON summary and prints concise RR-vs-PLRU delta report.

---

## 7) Core/Top Parameter Propagation and Build-System Support

### Updated RTL wrappers

- `rtl/ibex_top.sv`
- `rtl/ibex_top_tracing.sv`
- `rtl/ibex_lockstep.sv`
- `examples/simple_system/rtl/ibex_simple_system.sv`
- `dv/riscv_compliance/rtl/ibex_riscv_compliance.sv`
- `dv/uvm/core_ibex/tb/core_ibex_tb_top.sv`

### Updated direct icache TB instantiation

- `dv/uvm/icache/dv/tb/tb.sv`
  - Connected new perf outputs to local signals.

### Updated FuseSoC core files (to accept `ICachePLRU`)

- `ibex_core.core`
- `ibex_top.core`
- `ibex_top_tracing.core`
- `examples/simple_system/ibex_simple_system.core`
- `dv/verilator/simple_system_cosim/ibex_simple_system_cosim.core`
- `dv/riscv_compliance/ibex_riscv_compliance.core`

Added `ICachePLRU` parameter definitions and propagated into target parameter lists where required.

---

## 8) Documentation Update

### Updated file

- `doc/runningtests.md`

### Added section

- RR vs PLRU proxy-power flow:
  - build CoreMark
  - build/run RR config and save CSV/log
  - build/run PLRU config and save CSV/log
  - run `util/icache_proxy_energy.py`
  - expected outputs (`json` + stdout summary)

---

## 9) Validation Performed

### Successful checks

- Python script syntax:
  - `python3 -m py_compile util/icache_proxy_energy.py`
- Config parsing for both new configs:
  - `./util/ibex_config.py maxperf-pmp-bmfull-icache-rr-proxy fusesoc_opts`
  - `./util/ibex_config.py maxperf-pmp-bmfull-icache-plru-proxy fusesoc_opts`
- IDE lint diagnostics on touched files: no lint errors reported.

### Environment blocker

- Full cosim model build/run could not be completed in this environment due to missing tool:
  - `verilator: not found`
- FuseSoC pre-build requirements check fails until Verilator is available on `PATH`.

---

## 10) Final To-do Status

All requested implementation to-dos were completed:

- `cfg-surface` completed
- `rtl-policy-events` completed
- `rtl-plumbing` completed
- `pcount-export` completed
- `analysis-script` completed
- `docs-and-validate` completed (with documented external tool blocker for full run)

