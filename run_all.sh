#!/bin/bash
# run_all.sh — Run all icache optimizations through RR + PLRU co-simulation.
#
# For each variant (baseline + opt1–opt4), this script:
#   1. Swaps the ibex_icache.sv RTL in ibex/rtl/
#   2. Builds the co-simulation model (RR then PLRU)
#   3. Runs CoreMark under Spike co-simulation
#   4. Generates a proxy-energy JSON via icache_proxy_energy.py
#   5. Archives logs and results under results/<variant>/

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
IBEX_ROOT="$REPO_ROOT/ibex"
OPT_DIR="$REPO_ROOT/optimizations"
RESULTS_ROOT="$REPO_ROOT/results"
ICACHE_TARGET="$IBEX_ROOT/rtl/ibex_icache.sv"

declare -A VARIANTS
VARIANTS=(
  [baseline]="$OPT_DIR/baseline.sv"
  [opt1-linebuffer]="$OPT_DIR/opt1_line_buffer.sv"
  [opt2-fillbuffer]="$OPT_DIR/opt2_sequential_line_buffer.sv"
  [opt3-combined]="$OPT_DIR/opt3_combined.sv"
  [opt4-fb-threshold]="$OPT_DIR/opt4_fb_threshold.sv"
)

VARIANT_ORDER=(baseline opt1-linebuffer opt2-fillbuffer opt3-combined opt4-fb-threshold)

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
declare -A STATUS

usage() {
    echo "Usage: $0 [--setup] [--variant NAME] [--skip-existing]"
    echo "  --setup          Run CI dependency installation first"
    echo "  --variant NAME   Run only the specified variant"
    echo "  --skip-existing  Skip variants that already have results"
    exit 1
}

RUN_SETUP=false
ONLY_VARIANT=""
SKIP_EXISTING=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --setup)        RUN_SETUP=true; shift ;;
        --variant)      ONLY_VARIANT="$2"; shift 2 ;;
        --skip-existing) SKIP_EXISTING=true; shift ;;
        -h|--help)      usage ;;
        *)              echo "Unknown option: $1"; usage ;;
    esac
done

log() { echo "=== [$(date +%H:%M:%S)] $*"; }

# ─── Environment setup ──────────────────────────────────────────────────────
cd "$IBEX_ROOT"

if [ -f "ci/vars.env" ]; then
    set -a; source ci/vars.env; set +a
else
    echo "ERROR: ci/vars.env not found in $IBEX_ROOT" >&2
    exit 1
fi

if [ "$RUN_SETUP" = true ]; then
    log "Running build dependency installation..."
    ./ci/install-build-deps.sh
fi

export PATH="/tools/riscv/bin:/tools/riscv-isa-sim/bin:/tools/verible/bin:/tools/verilator/${VERILATOR_VERSION}/bin:$PATH"
export PKG_CONFIG_PATH="/tools/riscv-isa-sim/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"

log "Checking tools..."
python3 --version
fusesoc --version  || { echo "fusesoc not found"; exit 1; }
verilator --version || { echo "verilator not found"; exit 1; }
riscv32-unknown-elf-gcc --version || { echo "riscv32-unknown-elf-gcc not found"; exit 1; }

log "Building CoreMark..."
make -C ./examples/sw/benchmarks/coremark SUPPRESS_PCOUNT_DUMP=1

source ci/setup-cosim.sh

# ─── Run each variant ────────────────────────────────────────────────────────
run_variant() {
    local name="$1"
    local rtl_src="$2"
    local out_dir="$RESULTS_ROOT/$name"

    log "━━━ Starting variant: $name ━━━"

    if [ "$SKIP_EXISTING" = true ] && [ -f "$out_dir/icache_proxy_coremark.json" ]; then
        log "Skipping $name — results already exist"
        STATUS[$name]="SKIP"
        ((SKIP_COUNT++))
        return 0
    fi

    if [ ! -f "$rtl_src" ]; then
        log "ERROR: RTL source not found: $rtl_src"
        STATUS[$name]="FAIL"
        ((FAIL_COUNT++))
        return 1
    fi

    mkdir -p "$out_dir"
    cp "$rtl_src" "$ICACHE_TARGET"
    log "Swapped RTL → $(basename "$rtl_src")"

    cd "$IBEX_ROOT"

    # ── Round-Robin ──
    log "[$name] Building RR co-simulation model..."
    local RR_OPTS
    RR_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-rr-proxy fusesoc_opts)

    if ! fusesoc --cores-root=. run --target=sim --setup --build \
            lowrisc:ibex:ibex_simple_system_cosim $RR_OPTS; then
        log "ERROR: RR build failed for $name"
        STATUS[$name]="FAIL"
        ((FAIL_COUNT++))
        return 1
    fi

    log "[$name] Running RR simulation..."
    if ! ./ci/run-cosim-test.sh --skip-pass-check CoreMark \
            examples/sw/benchmarks/coremark/coremark.elf; then
        log "ERROR: RR simulation failed for $name"
        STATUS[$name]="FAIL"
        ((FAIL_COUNT++))
        return 1
    fi

    mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.rr.csv
    mv ibex_simple_system.log ibex_simple_system.rr.log

    # ── Pseudo-LRU ──
    log "[$name] Building PLRU co-simulation model..."
    local PLRU_OPTS
    PLRU_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-plru-proxy fusesoc_opts)

    if ! fusesoc --cores-root=. run --target=sim --setup --build \
            lowrisc:ibex:ibex_simple_system_cosim $PLRU_OPTS; then
        log "ERROR: PLRU build failed for $name"
        STATUS[$name]="FAIL"
        ((FAIL_COUNT++))
        return 1
    fi

    log "[$name] Running PLRU simulation..."
    if ! ./ci/run-cosim-test.sh --skip-pass-check CoreMark \
            examples/sw/benchmarks/coremark/coremark.elf; then
        log "ERROR: PLRU simulation failed for $name"
        STATUS[$name]="FAIL"
        ((FAIL_COUNT++))
        return 1
    fi

    mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.plru.csv
    mv ibex_simple_system.log ibex_simple_system.plru.log

    # ── Proxy energy report ──
    log "[$name] Generating proxy energy report..."
    if [ -f "util/icache_proxy_energy.py" ]; then
        python3 util/icache_proxy_energy.py \
            --rr ibex_simple_system_pcount.rr.csv \
            --plru ibex_simple_system_pcount.plru.csv \
            --out-json "$out_dir/icache_proxy_coremark.json"
    else
        log "WARNING: icache_proxy_energy.py not found — skipping JSON generation"
    fi

    # ── Archive logs ──
    cp -f ibex_simple_system_pcount.rr.csv  "$out_dir/"
    cp -f ibex_simple_system_pcount.plru.csv "$out_dir/"
    cp -f ibex_simple_system.rr.log  "$out_dir/"
    cp -f ibex_simple_system.plru.log "$out_dir/"

    log "[$name] ✓ Results saved to $out_dir/"
    STATUS[$name]="PASS"
    ((PASS_COUNT++))
}

for name in "${VARIANT_ORDER[@]}"; do
    if [ -n "$ONLY_VARIANT" ] && [ "$name" != "$ONLY_VARIANT" ]; then
        continue
    fi
    run_variant "$name" "${VARIANTS[$name]}" || true
done

# ─── Restore baseline RTL after all runs ─────────────────────────────────────
cp "$OPT_DIR/baseline.sv" "$ICACHE_TARGET"
log "Restored baseline RTL in ibex/rtl/"

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
log "━━━ Run Summary ━━━"
for name in "${VARIANT_ORDER[@]}"; do
    if [ -n "$ONLY_VARIANT" ] && [ "$name" != "$ONLY_VARIANT" ]; then
        continue
    fi
    printf "  %-25s %s\n" "$name" "${STATUS[$name]:-N/A}"
done
echo ""
log "PASS=$PASS_COUNT  FAIL=$FAIL_COUNT  SKIP=$SKIP_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi
