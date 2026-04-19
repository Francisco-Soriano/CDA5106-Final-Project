#!/bin/bash
# run_rr_plru_comparison.sh
# Automates the setup and execution of RR vs PLRU cache comparison tests for Ibex.
# Reference: ibex_edited/doc/runningtests.md

set -e

# Change to the directory of this script
cd "$(dirname "$0")"
IBEX_ROOT=$(pwd)

usage() {
    echo "Usage: $0 [--setup]"
    echo "  --setup  Run CI dependency installation and tool setup (requires sudo)"
    exit 1
}

RUN_SETUP=false
if [ "$1" == "--setup" ]; then
    RUN_SETUP=true
fi

echo "=== 1. Environment Setup ==="
# Load environment variables
if [ -f "ci/vars.env" ]; then
    set -a
    source ci/vars.env
    set +a
else
    echo "Error: ci/vars.env not found. Please run this script from the ibex_edited root."
    exit 1
fi

if [ "$RUN_SETUP" = true ]; then
    echo "Running build dependency installation (may prompt for sudo)..."
    ./ci/install-build-deps.sh
fi

# Set PATH for tools (using standard /tools/ installation paths)
export PATH="/tools/riscv/bin:/tools/riscv-isa-sim/bin:/tools/verible/bin:/tools/verilator/${VERILATOR_VERSION}/bin:$PATH"
export PKG_CONFIG_PATH="/tools/riscv-isa-sim/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"

# Check tool availability
echo "Checking tools..."
python3 --version
fusesoc --version || { echo "fusesoc not found in PATH. Try running with --setup"; exit 1; }
verilator --version || { echo "verilator not found in PATH. Try running with --setup"; exit 1; }
riscv32-unknown-elf-gcc --version || { echo "riscv32-unknown-elf-gcc not found in PATH. Try running with --setup"; exit 1; }

# Build CoreMark if not already built
echo "=== 2. Building CoreMark ==="
make -C ./examples/sw/benchmarks/coremark SUPPRESS_PCOUNT_DUMP=1

# Ensure Spike is correctly linked
source ci/setup-cosim.sh

echo "=== 3. Running Round-Robin (RR) Proxy Test ==="
IBEX_CONFIG_OPTS_RR=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-rr-proxy fusesoc_opts)

echo "Building RR co-simulation model..."
fusesoc --cores-root=. run --target=sim --setup --build \
    lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS_RR

echo "Executing RR simulation..."
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf

# Archive RR results
mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.rr.csv
mv ibex_simple_system.log ibex_simple_system.rr.log

echo "=== 4. Running Pseudo-LRU (PLRU) Proxy Test ==="
IBEX_CONFIG_OPTS_PLRU=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-plru-proxy fusesoc_opts)

echo "Building PLRU co-simulation model..."
fusesoc --cores-root=. run --target=sim --setup --build \
    lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS_PLRU

echo "Executing PLRU simulation..."
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf

# Archive PLRU results
mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.plru.csv
mv ibex_simple_system.log ibex_simple_system.plru.log

echo "=== 5. Generating Comparison Report ==="
if [ -f "util/icache_proxy_energy.py" ]; then
    python3 util/icache_proxy_energy.py \
      --rr ibex_simple_system_pcount.rr.csv \
      --plru ibex_simple_system_pcount.plru.csv \
      --out-json icache_proxy_coremark.json
    echo "Comparison complete. Results saved to icache_proxy_coremark.json"
else
    echo "Warning: util/icache_proxy_energy.py not found. Skipping final report generation."
fi

echo "=== Final Status ==="
echo "RR results: ibex_simple_system.rr.log"
echo "PLRU results: ibex_simple_system.plru.log"
