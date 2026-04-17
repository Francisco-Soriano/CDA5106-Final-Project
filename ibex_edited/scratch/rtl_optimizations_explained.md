# RTL Optimizations Explained

This document describes the three levels of RTL-level power optimizations implemented in the `RTL Optimized/` directory. All optimizations target the **Ibex I-Cache proxy energy metric**, which is dominated by SRAM tag and data reads (~97% of total energy).

---

## 1. Optimization Level 1: Basic Line Buffer
**File:** [`icache_optimization_1_coremark_line_buffer.sv`](file:///home/jordan/sp26/CDA5106-Final-Project/RTL%20Optimized/icache_optimization_1_coremark_line_buffer.sv)

### Overview
The baseline Ibex cache performs a parallel tag and data SRAM read on every lookup cycle, even for sequential instructions within the same cache line. Optimization 1 introduces a **Line Buffer** to exploit spatial locality.

### Mechanism
- **Capture:** Registers the Most Recently Used (MRU) cache line (data, tag, and way) after a successful SRAM hit.
- **Bypass:** On subsequent lookups, the incoming address is compared against the buffered line address. If they match (**same-line hit**), the SRAM `req` signals are suppressed.
- **Result:** Serves 8–16 instructions from a single SRAM read, reducing read events by ~50-60% for typical sequential code.

---

## 2. Optimization Level 2: Sequential Line Buffer (Wide Capture)
**File:** [`icache_optimization_2_coremark_sequential_line_buffer.sv`](file:///home/jordan/sp26/CDA5106-Final-Project/RTL%20Optimized/icache_optimization_2_coremark_sequential_line_buffer.sv)

### Overview
Level 2 improves the efficiency and safety of the Line Buffer to ensure higher capture rates in complex loops and better data integrity.

### Improvements over Level 1
- **Universal Capture:** While Level 1 might restrict capture to specific scenarios (like branch targets), Level 2 extends capture to **any** valid SRAM hit. This ensures the buffer is always populated during sequential execution.
- **Fill-Write Invalidation:** Adds logic to detect when a Fill Buffer writes a new line to the SRAM that conflicts with the currently buffered line. If a conflict is detected, the line buffer is invalidated to prevent serving stale data.
- **ECC Integration:** Refines the ECC data path to ensure that data served from the Line Buffer still benefits from error detection logic without requiring a redundant tag check.

---

## 3. Optimization Level 3: Combined Advanced Optimization
**File:** [`icache_optimization_3_coremark_combined_line_buffer_fb_throttle.sv`](file:///home/jordan/sp26/CDA5106-Final-Project/RTL%20Optimized/icache_optimization_3_coremark_combined_line_buffer_fb_throttle.sv)

### Overview
Level 3 is an "all-in" optimization strategy that combines the wide line buffer with two additional throughput-aware power-saving techniques.

### Included Techniques
1.  **Industrial-Grade Line Buffer:** The refined bypassing logic from Level 2.
2.  **Fill Buffer (FB) Lookup Suppression:**
    - Before issuing an SRAM read, the prefetcher checks if one of the 4 Fill Buffers is already fetching that specific line.
    - If a match is found, the SRAM read is suppressed because the data will eventually be delivered by the existing Fill Buffer anyway.
3.  **Prefetch Depth Throttling:**
    - **Tighter Threshold:** Tightens the standard `FB_THRESHOLD` from `NUM_FB-2` (2) down to `1`. This slows down the prefetcher when the pipe is full.
    - **Stall-Awareness:** Introduces `ICachePrefetchStallThrottle`. If the IF stage is stalled (output data is valid but `ready_i` is low), speculation is suppressed to avoid reading lines that might be flushed by an upcoming branch.

### Impact
This combined approach is estimated to reduce proxy energy by **over 60%** with negligible impact (approx. 0.6%) on CoreMark cycle counts.
