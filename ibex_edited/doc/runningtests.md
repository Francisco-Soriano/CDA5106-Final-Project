# Running tests locally

This repository’s “tests” are primarily **RTL lint + simulation/DV flows** driven through **FuseSoC**, plus **RISC‑V compliance** and a few **directed co-simulation** software tests. The public CI workflow in `.github/workflows/ci.yml` is the source of truth; the commands below mirror it.

## Quick start (Ubuntu / WSL2)

From the repository root:

```bash
# Load the pinned tool versions CI expects
set -a
source ci/vars.env
set +a

# Install build deps + prebuilt toolchain/verilator/verible
# Writes to /tools/*, so you will likely be prompted for sudo.
./ci/install-build-deps.sh

# CI uses $GITHUB_PATH; for local shells add tools to PATH manually.
# In particular, FuseSoC is installed into a Python venv at /tools/ibex-python-venv.
export PATH="/tools/ibex-python-venv/bin:/tools/riscv/bin:/tools/riscv-isa-sim/bin:/tools/verible/bin:/tools/verilator/${VERILATOR_VERSION}/bin:$PATH"
```

Sanity check:

```bash
python3 --version
fusesoc --version
verilator --version
riscv32-unknown-elf-gcc --version
verible-verilog-lint --version
```

## Run a minimal “smoke test”

Build and run the CSR testbench (this is a CI step and does not depend on `IBEX_CONFIG`):

```bash
fusesoc --cores-root=. run --target=sim --tool=verilator lowrisc:ibex:tb_cs_registers
```

## Run the public CI test flow (recommended)

### 1) Fetch the RISC‑V compliance suite (pinned)

```bash
mkdir -p build
cd build
git clone https://github.com/riscv/riscv-compliance.git
cd riscv-compliance
git checkout "$RISCV_COMPLIANCE_GIT_VERSION"
cd ../..
```

### 2) Build the directed software tests used by co-simulation

Use the same **`PATH`** as in **Quick start (Ubuntu / WSL2)** above so `riscv32-unknown-elf-gcc` resolves (typically `/tools/riscv/bin` after `ci/install-build-deps.sh`). If that compiler is missing from `PATH`, the CoreMark recipe fails with `riscv32-unknown-elf-gcc: No such file or directory` and **`examples/sw/benchmarks/coremark/coremark.elf` is never produced**.

```bash
# Build CoreMark without performance counter dump for co-simulation testing
make -C ./examples/sw/benchmarks/coremark SUPPRESS_PCOUNT_DUMP=1
make -C ./examples/sw/simple_system/pmp_smoke_test
make -C ./examples/sw/simple_system/dit_test
make -C ./examples/sw/simple_system/dummy_instr_test
```

Note: the CoreMark build will create `coremark.elf` and may also write `run1.log`/`run2.log` files
that are **instructions for running on hardware** (they do not contain results in this flow). When
you run CoreMark via co-simulation below, the **actual output/log** is written to
`ibex_simple_system.log` in the repository root.

### Run CoreMark in co-simulation

This flow is **Ibex Simple System** Verilator co-simulation with Spike (same style of bare-metal + UART software as in this repo). It is **not** the full **OpenTitan** top-level (e.g. Earl Grey) chip simulation; for that, use the OpenTitan tree and its software/build targets.

### Run CoreMark for OpenTitan (Earl Grey)

If your goal is to run CoreMark on the **OpenTitan top-level** (DV simulation, FPGA, or silicon),
use the **OpenTitan repository** and its software/test flow. This Ibex repository only builds the
benchmark ELF and supports the Ibex Simple System co-sim flow described above.

Recommended flow:

1. Build CoreMark in this repository (produces `coremark.elf`):

```bash
make -C ./examples/sw/benchmarks/coremark SUPPRESS_PCOUNT_DUMP=1
```

2. Use OpenTitan’s build/test targets from an OpenTitan checkout to run that benchmark in the
   desired environment (DV sim, FPGA, or silicon), following the OpenTitan book:
   - [OpenTitan documentation](https://opentitan.org/book/)
   - [OpenTitan repository](https://github.com/lowRISC/opentitan)

3. If you are running on hardware, `examples/sw/benchmarks/coremark/run1.log` and `run2.log`
   are expected setup hints from the benchmark runtime (for example, how `LOAD` is handled).
   They are not benchmark results by themselves.

In short: build `coremark.elf` here, then run it via OpenTitan’s own top-level software flow.

Order matters:

1. Build **`coremark.elf`** (section 2 above). Running `./ci/run-cosim-test.sh` before that produces `ERROR: Failed to load ELF file ... could not open file` and no `ibex_simple_system.log`.
2. Build the **`ibex_simple_system_cosim`** model (`Vibex_simple_system`) with FuseSoC (below).

Example for `maxperf-pmp-bmfull-icache`:

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache fusesoc_opts)

# So pkg-config can find Spike when building the co-sim DPI (adjust if Spike lives elsewhere)
export PKG_CONFIG_PATH="/tools/riscv-isa-sim/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"

# Build the co-sim model (this generates the Vibex_simple_system binary)
source ci/setup-cosim.sh
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS

# Run CoreMark (skip PASS check; we mostly care about the UART output / logs)
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
```

Keep **`PATH`** the same as in Quick start when running `fusesoc` and the co-sim binary (FuseSoC, Verilator, Spike, RISC-V tools).

This config is intentionally `SecureIbex=0`, so the security/DIT and dummy-instruction directed tests
(`dit_test` / `dummy_instr_test`) are not applicable; it’s focused on cache power/behavior work.

Results:
- UART output / pass-fail text ends up in `./ibex_simple_system.log`.

Common errors:

- **`Vibex_simple_system: No such file or directory`**: run the `fusesoc ... ibex_simple_system_cosim ... --setup --build` command above from the repository root (the binary is under `build/lowrisc_ibex_ibex_simple_system_cosim_0/sim-verilator/`).
- **`Failed to load ELF file ... could not open file`**: build CoreMark first (`make -C ./examples/sw/benchmarks/coremark SUPPRESS_PCOUNT_DUMP=1`) and confirm `examples/sw/benchmarks/coremark/coremark.elf` exists.
- **`riscv32-unknown-elf-gcc: No such file or directory`** when building CoreMark: add `/tools/riscv/bin` to `PATH` (see Quick start).
- **`grep: ibex_simple_system.log: No such file`** from `run-cosim-test.sh`: usually follows a failed simulator launch (e.g. missing ELF); fix the ELF path or rebuild the co-sim model.

### Cache power optimization: hit/miss proxies
This Simple System co-sim flow prints performance counters and also writes `ibex_simple_system_pcount.csv` at the end of the run.

In this repo, the performance-counter names exposed via `ibex_pcounts` include `Fetch Wait` (along with `Cycles`, `Instructions Retired`, etc.). At the moment, explicit "ICache hit" / "ICache miss" counters are not exported through `ibex_pcounts`.

A practical proxy workflow is:
- Run with `ICache=1` and compare `Fetch Wait` / `Cycles` against a run with `ICache=0` (or a different cache configuration).
- If you need actual hit/miss counts, you'll likely need to extend the counter/telemetry plumbing (or derive them from deeper tracing than what `ibex_pcounts` exports today).

### RR vs PLRU proxy-power flow

Use the dedicated proxy configs so runs only differ by I$ replacement policy:

- `maxperf-pmp-bmfull-icache-rr-proxy`
- `maxperf-pmp-bmfull-icache-plru-proxy`

Build CoreMark once:

```bash
make -C ./examples/sw/benchmarks/coremark SUPPRESS_PCOUNT_DUMP=1
```

Build and run RR:

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-rr-proxy fusesoc_opts)
source ci/setup-cosim.sh
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.rr.csv
mv ibex_simple_system.log ibex_simple_system.rr.log
```

Build and run PLRU:

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-plru-proxy fusesoc_opts)
source ci/setup-cosim.sh
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.plru.csv
mv ibex_simple_system.log ibex_simple_system.plru.log
```

Compare both runs:

```bash
python3 util/icache_proxy_energy.py \
  --rr ibex_simple_system_pcount.rr.csv \
  --plru ibex_simple_system_pcount.plru.csv \
  --out-json icache_proxy_coremark.json
```

Expected outputs:

- `icache_proxy_coremark.json` with per-run raw counters and derived metrics.
- stdout summary with RR-vs-PLRU deltas for cycles/instret/fetch-wait and proxy energy.

Cache-focused-but-not-security (`maxperf-pmp-bmfull-icache`)
Use `maxperf-pmp-bmfull-icache` to study instruction-cache behavior without mixing in the security hardening behavior controlled by `SecureIbex`:

- `ICache=1`
- `ICacheECC=1`
- `ICacheScramble=0`
- `SecureIbex=0` (so `dit_test` / `dummy_instr_test` are not applicable)

For the actual “build co-sim + run CoreMark” commands, use the example above.

### 3) Run the per-configuration CI steps

Use `maxperf-pmp-bmfull-icache` for this cache power/behavior flow.

Example for `maxperf-pmp-bmfull-icache`:

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache fusesoc_opts)

# Lint the top-level (Verilator + Verible)
fusesoc --cores-root . run --target=lint --tool=verilator   lowrisc:ibex:ibex_top_tracing $IBEX_CONFIG_OPTS
fusesoc --cores-root . run --target=lint --tool=veriblelint lowrisc:ibex:ibex_top_tracing $IBEX_CONFIG_OPTS

# Build a Verilator model for compliance testing
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_riscv_compliance $IBEX_CONFIG_OPTS

# Run the compliance suite (the loop matches CI)
export TARGET_SIM="$PWD/build/lowrisc_ibex_ibex_riscv_compliance_0.1/sim-verilator/Vibex_riscv_compliance"
export RISCV_PREFIX=riscv32-unknown-elf-
export RISCV_TARGET=ibex
export RISCV_DEVICE=rv32imc
for isa in rv32i rv32im rv32imc rv32Zicsr rv32Zifencei; do
  make -C build/riscv-compliance RISCV_ISA=$isa
done

# Co-simulation directed tests
export PKG_CONFIG_PATH="/tools/riscv-isa-sim/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
source ci/setup-cosim.sh
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
./ci/run-cosim-test.sh --skip-pass-check pmp_smoke examples/sw/simple_system/pmp_smoke_test/pmp_smoke_test.elf
```

With `SecureIbex=0`, `dit_test` and `dummy_instr_test` are not applicable for
`maxperf-pmp-bmfull-icache` (CI skips them for this reason).

## Notes / troubleshooting

- **`ci/install-build-deps.sh` expects Ubuntu 20.04/22.04**: it keys off `/etc/os-release`. On other distros you’ll need to install equivalent packages and set up the tools yourself.
- **`/tools/*` is created by the CI-style install script**: if you don’t want to write to `/tools`, you can adapt the script to install into a user directory, but the doc above intentionally mirrors CI.
- **New shell sessions**: export `PATH` (and `PKG_CONFIG_PATH` for co-sim builds) again, or CoreMark / FuseSoC steps will not find the pinned tools.

## Formal (optional)

The open-source formal flow is defined in `.github/workflows/ci-formal.yml` and uses a Nix dev environment (`nix print-dev-env .#oss-dev`) before running `dv/formal` targets.

