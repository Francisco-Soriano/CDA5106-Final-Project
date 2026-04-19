# I$ Proxy-Power Project How-To

This guide explains how to run the RR vs PLRU instruction-cache proxy-power workflow implemented in this project.

## What this project does

- Compares two I$ replacement policies:
  - `RR` (round-robin baseline)
  - `PLRU` (2-way pseudo-LRU)
- Captures I$ activity counters in `ibex_simple_system_pcount.csv`.
- Computes proxy energy metrics:
  - `E`
  - `E/inst`
  - `E/cycle`

Key references:

- Plan: `doc/projectplan.md`
- Implementation report: `doc/icache_proxy_implementation_report.md`
- General test flow: `doc/runningtests.md`

---

## 1) Prerequisites

From repo root:

```bash
set -a
source ci/vars.env
set +a
./ci/install-build-deps.sh
```

Set tool paths in your shell:

```bash
export PATH="/tools/ibex-python-venv/bin:/tools/riscv/bin:/tools/riscv-isa-sim/bin:/tools/verible/bin:/tools/verilator/${VERILATOR_VERSION}/bin:$PATH"
```

Sanity check:

```bash
python3 --version
fusesoc --version
verilator --version
riscv32-unknown-elf-gcc --version
```

If `verilator --version` fails, co-sim build will fail.

---

## 2) Build CoreMark

```bash
make -C ./examples/sw/benchmarks/coremark SUPPRESS_PCOUNT_DUMP=1
```

Expected artifact:

- `examples/sw/benchmarks/coremark/coremark.elf`

---

## 3) Run RR experiment

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-rr-proxy fusesoc_opts)
source ci/setup-cosim.sh
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.rr.csv
mv ibex_simple_system.log ibex_simple_system.rr.log
```

---

## 4) Run PLRU experiment

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-plru-proxy fusesoc_opts)
source ci/setup-cosim.sh
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.plru.csv
mv ibex_simple_system.log ibex_simple_system.plru.log
```

---

## 5) Compute proxy energy and compare

```bash
python3 util/icache_proxy_energy.py \
  --rr ibex_simple_system_pcount.rr.csv \
  --plru ibex_simple_system_pcount.plru.csv \
  --out-json icache_proxy_coremark.json
```

Outputs:

- `icache_proxy_coremark.json` (machine-readable summary)
- terminal summary with RR-vs-PLRU deltas

---

## 6) Counters expected in CSV

The CSV should include these I$ counters:

- `I$ Tag Array Reads`
- `I$ Data Array Reads`
- `I$ Tag Array Writes`
- `I$ Data Array Writes`
- `I$ Evictions`
- `I$ Invalidation Tag Writes`

If these are missing, check that:

- You used one of the new proxy configs.
- `MHPMCounterNum` in config is at least `19`.

---

## 7) Proxy metric definition

Default script weights:

- `w_tr = 1`
- `w_dr = 2`
- `w_tw = 2`
- `w_dw = 3`
- `w_ev = 1`
- `w_inv = 1`

Energy:

```text
E = 1*TagReads + 2*DataReads + 2*TagWrites + 3*DataWrites + 1*Evictions + 1*InvalTagWrites
```

Normalized metrics:

- `E/inst = E / InstructionsRetired`
- `E/cycle = E / Cycles`

---

## 8) Troubleshooting

- `verilator: not found`
  - Add Verilator to `PATH` (see Prerequisites).
- `Failed to load ELF file`
  - Rebuild CoreMark and verify `coremark.elf` exists.
- `Vibex_simple_system: No such file or directory`
  - Re-run the FuseSoC build command before `run-cosim-test.sh`.
- Config parsing errors
  - Regenerate options with:
    - `./util/ibex_config.py maxperf-pmp-bmfull-icache-rr-proxy fusesoc_opts`
    - `./util/ibex_config.py maxperf-pmp-bmfull-icache-plru-proxy fusesoc_opts`

