# Optimization Descriptions

This document details the five RTL variants of `ibex_icache.sv` used in this project. All variants are drop-in replacements stored in the `optimizations/` directory. The baseline includes performance counter instrumentation; each optimization builds on that instrumented baseline.

All four optimizations were generated through the LLM pipeline (see [ai_prompting.md](ai_prompting.md)). For Opt 4, the agent initially proposed sweeping changes; the human operator intervened and asked it to propose a small, non-destructive change instead, resulting in the single-constant tuning that proved most effective.

## Baseline

**File:** `optimizations/baseline.sv`

The stock Ibex I-cache with two additions:

1. **Performance counter output ports** (`perf_ic_tag_read_o`, `perf_ic_data_read_o`, `perf_ic_tag_write_o`, `perf_ic_data_write_o`, `perf_ic_evict_o`, `perf_ic_inval_tag_write_o`) for proxy energy measurement. See [performance_counters.md](performance_counters.md) for details.
2. **PLRU replacement policy option** (`ICachePLRU` parameter) alongside the existing round-robin policy.

The fill-buffer throttle threshold is set to the default value:

```systemverilog
localparam int FB_THRESHOLD = NUM_FB - 2;  // throttle when 3+ of 4 FBs active
```

This means the prefetcher only throttles non-branch lookups when 3 or more fill buffers are in use — a condition that rarely fires with CoreMark's ~98% cache hit rate.

## Opt 1 — Same-Line Line Buffer

**File:** `optimizations/opt1_line_buffer.sv`
**Co-sim status:** PASS

### Mechanism

Adds a single-entry **line buffer** that captures the most recently read cache line (data, tag, and way) after a successful SRAM hit.

On each subsequent lookup:
1. The incoming address is compared against the buffered line's address.
2. If they match (same cache line), the tag and data SRAM `req` signals are suppressed.
3. The buffered data is served directly, avoiding a redundant SRAM access.

### Expected Impact

For sequential instruction fetches within the same 256-bit cache line (8-16 instructions depending on compressed vs. uncompressed), each fetch after the first is served from the buffer. This should reduce tag and data reads by 50-60% in sequential code.

### Actual Results

A small but measurable proxy energy reduction on CoreMark: −0.002% for both RR and PLRU, corresponding to ~41 fewer tag/data SRAM reads per policy. This confirms the line buffer mechanism works — redundant same-line reads are being suppressed — but CoreMark's tight inner loops have very high cache hit rates with relatively few sequential same-line fetches, limiting the optimization's impact on this workload. The line buffer would likely show larger gains on workloads with longer sequential instruction streams or larger code footprints.

## Opt 2 — Sequential Line Buffer + Fill-Buffer Lookup Suppression

**File:** `optimizations/opt2_sequential_line_buffer.sv`
**Co-sim status:** FAIL (Spike co-simulation mismatch)

### Mechanism

Two enhancements over Opt 1:

1. **Universal capture**: The line buffer captures on **any** SRAM hit, not just branch targets or specific scenarios. This ensures the buffer stays populated during sequential execution.

2. **Fill-buffer lookup suppression**: Before issuing an SRAM read, the prefetcher checks whether any of the 4 fill buffers is already fetching the requested line. If a match is found, the SRAM lookup is suppressed because the data will eventually be delivered by the existing fill buffer.

Additional changes:
- **Fill-write invalidation**: Detects when a fill buffer writes a new line to SRAM that conflicts with the currently buffered line and invalidates the buffer to prevent stale data.
- **ECC integration**: Refines the ECC data path so data served from the line buffer still passes through error detection without a redundant tag check.

### Failure Analysis

This variant fails Spike co-simulation, producing instruction-level mismatches. The LLM-generated RTL introduced functional bugs in the complex interaction between fill-buffer suppression logic and the existing cache state machine. The exact failure mode involves incorrect data being served when fill-buffer and line-buffer states interact in corner cases.

## Opt 3 — Combined (Line Buffer + FB Suppression + Prefetch Throttle)

**File:** `optimizations/opt3_combined.sv`
**Co-sim status:** FAIL (Spike co-simulation mismatch)

### Mechanism

Combines all three power-saving techniques:

1. **Industrial-grade line buffer**: The refined bypassing logic from Opt 2.
2. **Fill-buffer lookup suppression**: Same as Opt 2 — skip SRAM reads when a fill buffer already handles the line.
3. **Prefetch depth throttling**:
   - Tightens `FB_THRESHOLD` from `NUM_FB - 2` (2) down to 1, throttling the prefetcher when 2+ fill buffers are active.
   - Introduces `ICachePrefetchStallThrottle`: if the IF stage is stalled (output data valid but `ready_i` low), speculative prefetching is suppressed to avoid reading lines that may be flushed by a branch.

### Failure Analysis

Like Opt 2, this variant fails co-simulation. Since it includes Opt 2's line buffer and fill-buffer suppression logic, it inherits the same functional bugs. The additional prefetch throttling logic may introduce further edge cases, but the root cause is the same problematic fill-buffer interaction.

### Projected Impact (Pre-Failure Estimate)

The original LLM analysis estimated >60% proxy energy reduction with ~0.6% cycle count increase. This could not be verified due to the functional failure.

## Opt 4 — Aggressive Fill-Buffer Threshold

**File:** `optimizations/opt4_fb_threshold.sv`
**Co-sim status:** PASS

### Background

After Opts 2 and 3 failed co-simulation due to the complexity of the LLM-generated changes, the human operator re-engaged the pipeline with an explicit constraint: propose a small, non-destructive change that tunes existing mechanisms rather than adding new logic. The agent identified the `FB_THRESHOLD` constant as a tuning knob and recommended lowering it.

### Mechanism

A single constant change — no new logic, no new signals, no data path modifications:

```systemverilog
localparam int FB_THRESHOLD = NUM_FB - 3;  // throttle when 2+ of 4 FBs active (was NUM_FB - 2)
```

With `NUM_FB = 4`, this changes the threshold from 2 to 1. The prefetcher now throttles non-branch lookups when **2 or more** fill buffers are active (previously required 3+).

### Why It Works

With a ~98% cache hit rate, fill buffers resolve in 1-2 cycles. The original threshold (2) almost never fired, allowing the prefetcher to run speculatively far ahead, reading SRAM for lines the core may never consume (especially after branches kill speculative work). Tightening to 1 keeps the prefetcher closer to the core's actual consumption.

Branch lookups bypass the throttle (`branch_i | ~lookup_throttle`), so branch penalty is unaffected.

### Safety

No new logic means no new functional risk:
- No data path changes
- No new signals or state
- The throttle mechanism already existed; this only tunes its activation point

### Results

| Metric | Baseline | Opt 4 | Change |
|--------|----------|-------|--------|
| **RR Proxy Energy** | 6,009,210 | 5,155,717 | **-14.2%** |
| **PLRU Proxy Energy** | 5,992,432 | 5,142,614 | **-14.2%** |
| RR Tag/Data Reads | 1,937,660 | 1,658,674 | -14.4% |
| PLRU Tag/Data Reads | 1,938,044 | 1,658,488 | -14.4% |
| RR Cycles | 3,113,043 | 3,134,418 | +0.7% |
| PLRU Cycles | 3,112,363 | 3,131,839 | +0.6% |
| RR Fetch Wait | 163,673 | 185,245 | +13.2% |
| PLRU Fetch Wait | 162,993 | 182,658 | +12.1% |
| Instructions Retired | 2,754,578 | 2,754,578 | 0% |

The ~14% proxy energy reduction comes from ~280K fewer SRAM reads per configuration. The cost is a modest 0.6-0.7% increase in total cycles and a 12-13% increase in fetch-wait cycles (expected: tighter throttle = slightly more stalls when multiple fill buffers are active).

## Summary

| Variant | Approach | Co-sim | Proxy Energy Δ | Source |
|---------|----------|--------|-----------------|--------|
| Baseline | Stock + counters | PASS | — | Manual |
| Opt 1 | Same-line line buffer | PASS | -0.002% | LLM |
| Opt 2 | Seq. line buffer + FB suppression | FAIL | — | LLM |
| Opt 3 | Combined (all techniques) | FAIL | — | LLM |
| Opt 4 | Aggressive FB_THRESHOLD | PASS | **-14.2%** | LLM (human-constrained) |

**Key finding:** Only 2 of 4 LLM-generated RTL optimizations produce functionally correct hardware. The simpler the change (Opt 1: buffer logic; Opt 4: one constant), the more likely it is correct. Complex multi-mechanism changes (Opts 2-3) introduced subtle functional bugs that break instruction-level verification against the ISA simulator. Notably, the most successful optimization (Opt 4) came from re-engaging the LLM with an explicit constraint to make a minimal, non-destructive change after the complex attempts failed — demonstrating that human-guided constraints are critical for effective LLM-assisted RTL design.
