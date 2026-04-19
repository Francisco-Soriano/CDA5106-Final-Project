# CDA 5106 Final Project — CORE: Cache Optimization and Reasoning Agent for Power Efficiency

Central Processing Units (CPUs) perform massive amounts of operations but waste significant energy moving data, even with caches. Existing cache optimization work mainly focuses on performance (miss rate, latency) rather than power. CORE is an RTL optimization framework that uses off-chip LLMs and performance counters (reads, writes, evictions) as power proxies to track and reduce cache energy. In an Ibex instruction-cache case study, only some AI-generated optimizations were valid, but a prefetch-throttling approach achieved a 14.2% energy reduction with minimal performance impact, highlighting both the high potential and remaining unreliability of LLM-driven RTL design — specifically in terms of power.

## Repository Layout

```
├── ibex/                     # Ibex core (modified with performance counters)
│   └── rtl/ibex_icache.sv    # Baseline icache RTL (restored to stock thresholds)
├── optimizations/            # All RTL variants (drop-in replacements for ibex_icache.sv)
│   ├── baseline.sv           # Stock icache + perf counters (FB_THRESHOLD = NUM_FB - 2)
│   ├── opt1_line_buffer.sv   # Same-line line buffer
│   ├── opt2_sequential_line_buffer.sv  # Sequential line buffer + fill-buffer suppression
│   ├── opt3_combined.sv      # Combined: line buffer + FB suppression + prefetch throttle
│   └── opt4_fb_threshold.sv  # Aggressive fill-buffer threshold (FB_THRESHOLD = NUM_FB - 3)
├── results/                  # Archived per-variant simulation results (JSON + logs)
├── docs/                     # Project documentation
├── rtla-synthesis/           # Separate ALU synthesis experiments
├── run_all.sh                # Automated script: swap RTL → build → cosim → collect results
├── compare_results.py        # Load all result JSONs and print a comparison table
└── README.md
```

## Documentation

Detailed documentation is in the [`docs/`](docs/) directory:

- **[Performance Counters](docs/performance_counters.md)** — The 6 I-cache event pulses added to Ibex, how they propagate from `ibex_icache.sv` through the MHPM counter infrastructure to CSV export, CSR index mapping, and all files modified.
- **[Methodology](docs/methodology.md)** — The proxy energy formula and default weights, RR vs PLRU replacement policy configurations, the end-to-end measurement pipeline, result artifact formats (JSON, CSV, logs), and limitations.
- **[Optimizations](docs/optimizations.md)** — Detailed descriptions of all 5 RTL variants (baseline + opts 1-4), including mechanisms, failure analysis for opts 2-3, and full results tables for passing variants.
- **[AI Prompting](docs/ai_prompting.md)** — The three-agent LLM pipeline (Planner/Designer/Reviewer), prompt templates, how they were applied, and lessons learned from 2-of-4 failures.

Additional reference documentation lives in [`ibex/doc/`](ibex/doc/):

- [`runningtests.md`](ibex/doc/runningtests.md) — Low-level build and test commands (FuseSoC, compliance suite, co-sim)
- [`projectplan.md`](ibex/doc/projectplan.md) — Original proxy energy plan with counter index mapping and LLM prompt template
- [`icache_proxy_implementation_report.md`](ibex/doc/icache_proxy_implementation_report.md) — Implementation changelog for the performance counter work

## Optimizations

| Variant | Approach | Source | Co-sim | Proxy Energy Δ |
|---------|----------|--------|--------|-----------------|
| Baseline | Stock icache + perf counters | Manual | PASS | — |
| Opt 1 | Same-line line buffer | LLM | PASS | -0.002% |
| Opt 2 | Sequential line buffer + FB suppression | LLM | FAIL | — |
| Opt 3 | Combined (all techniques) | LLM | FAIL | — |
| Opt 4 | Aggressive `FB_THRESHOLD = NUM_FB - 3` | LLM (constrained) | PASS | **-14.2%** |

See [docs/optimizations.md](docs/optimizations.md) for detailed descriptions, mechanisms, failure analysis, and full results.

## Running Simulations

### Prerequisites
- RISC-V toolchain (`riscv32-unknown-elf-gcc`)
- Verilator (version specified in `ibex/ci/vars.env`)
- FuseSoC
- Spike (RISC-V ISA simulator, for co-simulation)
- Python 3

Run `./run_all.sh --setup` once to install build dependencies (requires sudo).

### Run All Variants

```bash
./run_all.sh
```

This iterates through baseline + all 4 optimizations.  For each variant it:
1. Swaps `ibex/rtl/ibex_icache.sv` with the variant RTL
2. Builds the Verilator co-simulation model (RR and PLRU replacement policies)
3. Runs CoreMark under Spike co-simulation
4. Generates `icache_proxy_coremark.json` with proxy-energy metrics
5. Archives results under `results/<variant>/`

After all runs, the baseline RTL is automatically restored.

Options:
- `--variant NAME` — run only one variant (e.g., `--variant opt3-combined`)
- `--skip-existing` — skip variants whose results already exist

### Compare Results

```bash
python3 compare_results.py
```

Prints a table comparing all variants against the baseline, showing counters, proxy energy, percentage deltas, and pass/fail status.

## Results Summary

Proxy energy measured via `icache_proxy_energy.py` on CoreMark (weights: tag_read=1, data_read=2, tag_write=2, data_write=3, eviction=1):

| Variant | RR Proxy Energy | Δ RR | PLRU Proxy Energy | Δ PLRU | Co-sim Status |
|---------|-----------------|------|-------------------|--------|---------------|
| Baseline | 6,009,210 | — | 5,992,432 | — | PASS |
| Opt 1: Line buffer | 6,009,087 | −0.002% | 5,992,312 | −0.002% | PASS |
| Opt 2: Seq. LB + FB supp. | — | — | — | — | FAIL |
| Opt 3: Combined | — | — | — | — | FAIL |
| Opt 4: FB threshold | 5,155,717 | **−14.20%** | 5,142,614 | **−14.18%** | PASS |

Opts 2 and 3 fail Spike co-simulation verification, meaning the LLM-generated RTL changes introduced functional bugs that break instruction-level correctness.  This is a key finding: only 2 of 4 AI-generated optimizations produce functionally correct hardware.

Of the passing variants, Opt 4 (aggressive `FB_THRESHOLD = NUM_FB - 3`) achieves the largest reduction: **~14% lower proxy energy** with a modest increase in fetch-wait cycles due to throttled speculative prefetches.  Opt 1 achieves a small but measurable reduction (~41 fewer SRAM reads per policy), confirming the line buffer mechanism works; the limited improvement is because CoreMark's tight loops already exhibit high cache hit rates with few redundant same-line fetches.

## Contact

- Jordan Merkel — jo045021@ucf.edu
- Alexander Garcia — al743857@ucf.edu
- Julian Vasquez — ju081309@ucf.edu
- Francisco Soriano — fr015568@ucf.edu
