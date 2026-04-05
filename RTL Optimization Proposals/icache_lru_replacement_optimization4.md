---
name: ICache LRU Replacement
overview: Enable the PLRU replacement policy that is already fully implemented in rtl/ibex_icache.sv by flipping the ICachePLRU parameter from 0 to 1. No RTL logic needs to be written.
todos:
  - id: enable-plru-param
    content: Set ICachePLRU = 1'b1 at the ibex_icache instantiation site in rtl/ibex_top.sv (or change the module default) to activate the existing PLRU logic
    status: pending
  - id: lru-lint
    content: Run Verilator lint on ibex_top_tracing with maxperf-pmp-bmfull-icache config to verify no errors
    status: pending
  - id: lru-measure
    content: Run CoreMark co-sim before and after, compare Evictions, TagWrites, DataWrites in ibex_simple_system_pcount.csv
    status: pending
isProject: false
---

# ICache PLRU Replacement Policy

## What Was Found in the RTL

The RTL already contains a complete PLRU implementation. No new logic needs to be written.
The only file that needs a change is wherever `ibex_icache` is instantiated (typically
[`rtl/ibex_top.sv`](rtl/ibex_top.sv)) — or the module parameter default itself.

Existing signals already in [`rtl/ibex_icache.sv`](rtl/ibex_icache.sv):

```systemverilog
// Module parameter (already present)
parameter bit ICachePLRU = 1'b0

// Already declared
logic [IC_NUM_LINES-1:0] plru_mru_way_q;  // 256-bit per-set MRU state
logic [IC_NUM_WAYS-1:0]  plru_way_ic1;    // one-hot PLRU eviction way
logic [IC_NUM_WAYS-1:0]  repl_way_ic1;    // mux: PLRU or round-robin

// Already implemented
assign plru_way_ic1 = plru_mru_way_q[lookup_index_ic1] ? 2'b01 : 2'b10;
assign repl_way_ic1 = ICachePLRU ? plru_way_ic1 : round_robin_way_q;
assign sel_way_ic1  = |tag_invalid_ic1 ? lowest_invalid_way_ic1 : repl_way_ic1;

always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) begin
    plru_mru_way_q <= '0;
  end else if (lookup_valid_ic1) begin
    if (tag_hit_ic1) begin
      plru_mru_way_q[lookup_index_ic1] <= tag_match_ic1[1];  // mark hit way as MRU
    end else begin
      plru_mru_way_q[lookup_index_ic1] <= sel_way_ic1[1];    // mark evicted way as MRU
    end
  end
end
```

## The Only Change Needed

Find the `ibex_icache` instantiation and change the `ICachePLRU` parameter:

Old:
```systemverilog
ibex_icache #(
  .ICachePLRU   (1'b0),
  ...
```

New:
```systemverilog
ibex_icache #(
  .ICachePLRU   (1'b1),
  ...
```

Alternatively, change the default in the module header directly (line ~15 of `rtl/ibex_icache.sv`):
```systemverilog
parameter bit ICachePLRU = 1'b1   // was 1'b0
```

When `ICachePLRU = 1`, synthesis eliminates `round_robin_way_q` and `round_robin_way_ic1`
as dead logic — those registers stop toggling at no cost.

## How the PLRU Works

- `plru_mru_way_q[index]` = 0 → way0 is MRU → evict way1 next miss
- `plru_mru_way_q[index]` = 1 → way1 is MRU → evict way0 next miss
- Updated on every IC1 result (`lookup_valid_ic1`): hit → mark hit way as MRU; miss → mark evicted way as MRU
- On reset: all sets default to way0 as MRU (way1 evicted first) — safe cold-start behavior

## Power and Performance Impact

| Counter | Effect | Reason |
|---|---|---|
| Evictions | Decreases | PLRU keeps recently used lines, reducing conflict evictions |
| TagWrites | Decreases | Fewer evictions → fewer fill buffer tag writebacks |
| DataWrites | Decreases | Fewer evictions → fewer fill buffer data writebacks |
| TagReads | No change | Both ways always read on every lookup |
| DataReads | No change | Read policy unchanged |
| InvalTagWrites | No change | Invalidation is independent |

Additional power saving: when `ICachePLRU = 1`, synthesis removes `round_robin_way_q` (2 bits
toggling every `lookup_valid_ic1`). The `plru_mru_way_q` array only changes 1 bit per cycle
(the bit for the currently accessed set index).

## Verification

Run lint first:
```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache fusesoc_opts)
fusesoc --cores-root . run --target=lint --tool=verilator lowrisc:ibex:ibex_top_tracing $IBEX_CONFIG_OPTS
```

Then run CoreMark before and after:
```bash
./ci/run-cosim-test.sh --skip-pass-check CoreMark \
    examples/sw/benchmarks/coremark/coremark.elf
cat ibex_simple_system_pcount.csv
```

Watch: **Evictions**, **TagWrites**, **DataWrites** should all decrease.
**TagReads**, **DataReads**, **InvalTagWrites** should be unchanged.
