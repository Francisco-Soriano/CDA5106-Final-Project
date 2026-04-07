---
name: ICache Power Optimization Plan
overview: Three RTL-level optimizations for ibex_icache.sv targeting the proxy energy metric, with the Line Buffer technique offering the largest single reduction (50-80% of read energy) by exploiting spatial locality within cache lines.
todos:
  - id: deep-dive-opt1
    content: "Deep-dive plan for Optimization 1 (Line Buffer): full signal list, edge cases, reset conditions"
    status: pending
  - id: deep-dive-opt2
    content: "Deep-dive plan for Optimization 2 (Fill Buffer Lookup Suppression): comparator logic, FB interaction"
    status: pending
  - id: deep-dive-opt3
    content: "Deep-dive plan for Optimization 3 (Prefetch Depth Throttling): threshold tuning, stall-aware gating"
    status: pending
  - id: implement-opt1
    content: Designer implementation of Optimization 1 in ibex_icache.sv
    status: pending
  - id: implement-opt2
    content: Designer implementation of Optimization 2 in ibex_icache.sv
    status: pending
  - id: implement-opt3
    content: Designer implementation of Optimization 3 in ibex_icache.sv
    status: pending
  - id: review-all
    content: Reviewer pass on all three optimized RTL files
    status: pending
isProject: false
---

# Ibex ICache Power Optimization Plan

## Baseline Power Profile Analysis

Source: [icache_proxy_coremark.json](ibex_edited/icache_proxy_coremark.json), weights from [icache_proxy_energy.py](ibex_edited/util/icache_proxy_energy.py).

The proxy energy formula is:

```
E = 1.0*tag_reads + 2.0*data_reads + 2.0*tag_writes + 3.0*data_writes + 1.0*evictions + 1.0*inval_tag_writes
```

**RR Baseline Breakdown (total = 6,009,210):**

- Data reads:  2.0 x 1,937,660 = 3,875,320 **(64.5%)**
- Tag reads:   1.0 x 1,937,660 = 1,937,660 **(32.2%)**
- Data writes: 3.0 x 39,246    = 117,738   (2.0%)
- Tag writes:  2.0 x 39,246    = 78,492    (1.3%)
- Evictions + Inval: 0

**Critical Insight:** `tag_reads == data_reads` in both configurations. This means every tag lookup performs a simultaneous data lookup (parallel tag-data access in IC0, lines 274-288 of [ibex_icache.sv](ibex_edited/rtl/ibex_icache.sv)). **96.7% of all proxy energy comes from read events.** Write optimization is near-irrelevant for this workload.

The perf counters are one-pulse-per-event:

```systemverilog
assign perf_ic_tag_read_o  = tag_req_ic0 & ~tag_write_ic0;   // line 345
assign perf_ic_data_read_o = data_req_ic0 & ~data_write_ic0;  // line 346
```

Therefore, the only way to reduce proxy energy meaningfully is to **reduce the number of cycles where `tag_req_ic0` / `data_req_ic0` fire as reads**. All three optimizations below target this.

---

## Optimization 1: Line Buffer (Same-Line Hit Suppression)

**Mechanism:** Register the tag, index, data, and validity of the most recently fetched cache line. On each new lookup, compare the incoming address's line-address bits against the buffered tag+index. If they match (sequential fetch within the same 32-byte line), bypass the SRAM entirely and serve from the register.

**Why it works:** A 32-byte cache line holds 8-16 RISC-V instructions (mix of 16-bit compressed and 32-bit). Sequential code traverses a full line before needing the next one. In CoreMark, ~60-80% of lookups are within the same line as the previous hit, making the vast majority of SRAM reads redundant.

**Key signals to modify in [ibex_icache.sv](ibex_edited/rtl/ibex_icache.sv):**

- **New registers:** `line_buf_tag_q` (tag+index of buffered line), `line_buf_data_q` (full line data), `line_buf_valid_q` (1-bit)
- **New signal:** `line_buf_hit_ic0` = `line_buf_valid_q & (lookup_addr_ic0[ADDR_W-1:IC_LINE_W] == line_buf_tag_q)`
- **Gate lookups (line ~254):** Modify `lookup_req_ic0` or introduce a new `sram_lookup_req_ic0` that is suppressed when `line_buf_hit_ic0` is true. The FB allocation and prefetch-address advancement must still proceed.
- **Gate SRAM reads (lines 274, 285):** Ensure `tag_req_ic0` and `data_req_ic0` do not fire for lookups served by the line buffer.
- **Capture (line ~395-402):** On IC1 cache hit (`lookup_valid_ic1 & tag_hit_ic1`), latch `hit_data_ecc_ic1` and `{lookup_addr_ic1, lookup_index_ic1}` into the line buffer registers.
- **Invalidate:** Clear `line_buf_valid_q` on `branch_i`, `icache_inval_i`, `~icache_enable_i`, or any line buffer address conflict with a fill write.
- **Output mux (line ~942):** Add the line buffer as a data source in the `line_data` mux, selected when `line_buf_hit_ic0` was true for that FB.

**Expected impact:** Conservatively 50-60% reduction in tag_reads and data_reads.

- Saved tag reads: ~1,160,000. Saved data reads: ~1,160,000.
- Energy saved: 1.0 x 1.16M + 2.0 x 1.16M = ~3.48M
- **New proxy energy: ~2.5M (approx. 58% reduction)**

---

## Optimization 2: Fill Buffer Lookup Suppression

**Mechanism:** Before issuing an SRAM lookup in IC0, compare the lookup address (line-aligned) against the addresses of all active fill buffers. If any fill buffer is already fetching that cache line, suppress the tag and data SRAM reads. The fill buffer's own output path (`fill_out_data`, `fill_out_arb`) will deliver the data when it arrives.

**Why it works:** When a cache miss occurs, the fill buffer fetches the line over multiple beats. During this window, the prefetcher may issue 1-4 additional lookups to the same line (sequential fetches). These lookups read the SRAM, miss (the line isn't cached yet), and allocate new fill buffers that ultimately discover the data is already being fetched. All those tag+data reads are wasted.

**Key signals to modify:**

- **New comparators:** For each FB `fb` (0..NUM_FB-1), compare `lookup_addr_ic0[ADDR_W-1:IC_LINE_W]` against `fill_addr_q[fb][ADDR_W-1:IC_LINE_W]`, qualified by `fill_busy_q[fb]`.
- **New signal:** `fill_match_ic0 = |(fill_busy_q & fill_addr_line_match)` -- true when any active FB covers this line.
- **Gate SRAM reads (lines 274, 285):** Modify `tag_req_ic0` and `data_req_ic0` to exclude the lookup component when `fill_match_ic0` is true. Fills, invalidations, and ECC writes are unaffected.
- **Preserve FB allocation:** `lookup_grant_ic0` and `fill_new_alloc` should still fire so the prefetcher advances. The new FB will discover the match via the existing `fill_in_ic1` / `fill_hit_ic1` path or be fast-forwarded data from the active FB.
- **IC1 gating (line 355):** Ensure `lookup_valid_ic1` is gated (or the new FB's IC1 hit-check is skipped) when the SRAM was not actually read.

**Expected impact:** Approximately 2-8% reduction, depending on miss rate and line fill duration.

- ~39K misses x ~2-4 redundant lookups each = ~80K-160K saved read events
- Energy saved: 80K-160K x (1.0 + 2.0) = ~240K-480K
- **New proxy energy: ~5.5M-5.8M (approx. 4-8% reduction)**

---

## Optimization 3: Prefetch Depth Throttling

**Mechanism:** Tighten the existing `lookup_throttle` mechanism (line 252) to suppress speculative prefetch lookups earlier, reducing total SRAM read events at the cost of slightly higher `fetch_wait` cycles.

**Why it works:** The current throttle only activates when `fb_fill_level > FB_THRESHOLD` (i.e., 3+ of 4 FBs are busy). In practice with a 98% hit rate, FBs are allocated and released within 1-2 cycles (hit path), so the throttle rarely fires. Meanwhile, the prefetcher aggressively looks up the next cache line even when the IF stage is stalled or has plenty of buffered data. These speculative reads cost energy with diminishing performance return.

**Key signals to modify:**

- **Lower `FB_THRESHOLD` (line 80):** Reduce from `NUM_FB - 2` (=2) to `1` or even `0`. This throttles lookups as soon as 2+ (or 1+) FBs are active, reducing speculative depth.
- **Add output-aware throttle (line ~254):** Add a condition that suppresses non-branch lookups when valid output data is already available and the IF stage is stalled: e.g., `~(data_valid & ~ready_i)` or `~(output_valid_q & ~ready_i)`.
- **Preserve branch responsiveness:** All throttling should be bypassed on `branch_i` to avoid increasing branch penalty. The existing `(branch_i | ~lookup_throttle)` structure (line 254) already handles this.
- **Tunable parameter:** Consider making the throttle depth a module parameter so different power-performance tradeoffs can be explored.

**Expected impact:** 5-20% reduction in tag_reads and data_reads, depending on aggressiveness. More aggressive throttling trades read savings for increased `fetch_wait`.

- Conservative (FB_THRESHOLD=1): ~10% fewer reads, minimal perf impact
- Aggressive (FB_THRESHOLD=0 + stall suppression): ~20% fewer reads, ~5-10% more fetch_wait cycles
- Energy saved (conservative): 194K x (1.0 + 2.0) = ~580K
- **New proxy energy: ~5.4M (approx. 10% reduction)**

---

## Summary: Expected Combined Impact

Optimizations 1, 2, and 3 are orthogonal and can be combined. With the line buffer dominating:

- **Opt 1 alone:** ~50-60% proxy energy reduction
- **Opt 1 + 2:** ~55-65% reduction  
- **Opt 1 + 2 + 3:** ~60-70% reduction

All changes are confined to [ibex_icache.sv](ibex_edited/rtl/ibex_icache.sv). No other files require modification.