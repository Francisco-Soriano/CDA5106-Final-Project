# ICache Optimization Notes

## Change Made (ibex_icache.sv, line 82)

Single constant change — tighter prefetch throttle threshold:

```
FB_THRESHOLD = NUM_FB - 2   →   FB_THRESHOLD = NUM_FB - 3
```

This changes the threshold from 2 to 1 (with NUM_FB=4). The prefetcher now
throttles non-branch lookups when 2+ fill buffers are active (was 3+).

**Why it works:** With a 98% cache hit rate, fill buffers resolve in 1-2 cycles.
The original threshold (2) almost never fired, allowing the prefetcher to run
speculatively far ahead, reading the SRAM for lines the core may never consume
(especially after branches kill speculative work). Tightening to 1 keeps the
prefetcher closer to the core's actual consumption. Branch lookups still bypass
the throttle (`branch_i | ~lookup_throttle`), so branch penalty is unaffected.

**Safety:** No new logic, no new signals, no data path changes. Just
architectural tuning of an existing throttle mechanism.

## Results Comparison

### PLRU (best policy)

| Metric | Baseline | Optimized | Change |
|--------|----------|-----------|--------|
| proxy_energy | 5,992,432 | 5,142,614 | **-14.2%** |
| proxy_energy_per_inst | 2.175 | 1.867 | **-14.2%** |
| tag_reads | 1,938,044 | 1,658,488 | -14.4% |
| data_reads | 1,938,044 | 1,658,488 | -14.4% |
| tag_writes | 35,660 | 33,430 | -6.3% |
| data_writes | 35,660 | 33,430 | -6.3% |
| cycles | 3,112,363 | 3,131,839 | +0.6% |
| fetch_wait | 162,993 | 182,658 | +12.1% |
| instret | 2,754,578 | 2,754,578 | 0% |

### RR

| Metric | Baseline | Optimized | Change |
|--------|----------|-----------|--------|
| proxy_energy | 6,009,210 | 5,155,717 | **-14.2%** |
| proxy_energy_per_inst | 2.182 | 1.872 | **-14.2%** |
| tag_reads | 1,937,660 | 1,658,674 | -14.4% |
| data_reads | 1,937,660 | 1,658,674 | -14.4% |
| cycles | 3,113,043 | 3,134,418 | +0.7% |
| fetch_wait | 163,673 | 185,245 | +13.2% |

## Summary

- **14.2% proxy energy reduction** from a single constant change
- ~280K fewer SRAM reads per configuration
- +0.6-0.7% cycles (negligible performance cost)
- +12-13% fetch_wait (expected: tighter throttle = slightly more stalls)
- CoreMark passes with co-simulation verification
