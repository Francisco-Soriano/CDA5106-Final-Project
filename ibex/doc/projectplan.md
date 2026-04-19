# I$ power-proxy optimization plan (RR vs PLRU)

This document is a shareable end-to-end plan for evaluating **instruction-cache (I$)** replacement policy changes in Ibex using a **proxy-only power metric** derived from **hardware performance counters** (no external power tools).

## Scope and baseline

- **Target RTL**: instruction cache in [`rtl/ibex_icache.sv`](../rtl/ibex_icache.sv)
- **Evaluation flow**: Simple System co-simulation (`lowrisc:ibex:ibex_simple_system_cosim`)
- **Workload baseline**: CoreMark run via co-sim
- **Baseline config**: `maxperf-pmp-bmfull-icache` as the starting point, extended into two experimental configs (RR vs PLRU) so runs differ only by victim policy.

## What we are measuring (proxy energy)

We define a proxy energy score \(E\) computed from event counters that approximate I$ array activity:

\[
E = w_{tr}\cdot TagReads + w_{dr}\cdot DataReads + w_{tw}\cdot TagWrites + w_{dw}\cdot DataWrites + w_{ev}\cdot Evictions + w_{inv}\cdot InvalTagWrites
\]

Default weights used by the analysis script (data-biased):

- \(w_{tr}=1\) (TagReads)
- \(w_{dr}=2\) (DataReads)
- \(w_{tw}=2\) (TagWrites)
- \(w_{dw}=3\) (DataWrites)
- \(w_{ev}=1\) (Evictions)
- \(w_{inv}=1\) (InvalTagWrites)

Report normalized metrics as well:

- **E/inst** = \(E / InstructionsRetired\)
- **E/cycle** = \(E / Cycles\)

## Replacement policies

Ibex I$ is **2-way set associative** (`IC_NUM_WAYS=2`), so we implement and compare:

- **RR (round-robin)**: current baseline behavior; when allocating into a full set, alternate victim way using the existing global round-robin state.
- **PLRU (2-way)**: track a **1-bit per set MRU**; on replacement, evict the opposite way.

Important: both policies keep **invalid-first allocation** (if any way is invalid, allocate there and do not count an eviction).

## Event definitions (what gets counted)

We add explicit one-cycle event pulses in the I$ at the point where RAM activity is unambiguous:

- **TagReads**: a tag RAM request that is *not* a tag write
- **TagWrites**: tag write enable asserted
- **DataReads**: a data RAM request that is *not* a data write
- **DataWrites**: data write enable asserted
- **Evictions**: a cache allocation that overwrites a previously-valid line (i.e., allocation occurs and there were no invalid ways in that set)
- **InvalTagWrites**: invalidation sweep writes to the tag RAM

### Why “evictions” are handled carefully

“Picking a victim way” is not the same thing as “evicting”. We count an eviction only when a fill buffer actually **commits an allocation write** into the cache and the victim way was valid (set was full).

## Counter plumbing overview (RTL → CSV)

The co-sim model already prints counters and writes `ibex_simple_system_pcount.csv` at end of run. We extend that path to include the I$ events.

```mermaid
flowchart TD
  icache[rtl/ibex_icache.sv] -->|event_pulses| ifStage[rtl/ibex_if_stage.sv]
  ifStage -->|event_pulses| core[rtl/ibex_core.sv]
  core -->|inputs| csrs[rtl/ibex_cs_registers.sv]
  csrs -->|mhpmcounter_get()| pcountCpp[dv/verilator/pcount/cpp/ibex_pcounts.cc]
  pcountCpp -->|writes_csv| csv[ibex_simple_system_pcount.csv]
  csv -->|parse| script[util/icache_proxy_energy.py]
  script -->|json+summary| report[RR_vs_PLRU_report]
```

## Counter index plan (adds only; does not disturb existing counters)

Existing counters occupy indices 0..12 today (see `mhpmcounter_incr` assignments in
[`rtl/ibex_cs_registers.sv`](../rtl/ibex_cs_registers.sv) and the name list in
[`dv/verilator/pcount/cpp/ibex_pcounts.cc`](../dv/verilator/pcount/cpp/ibex_pcounts.cc)).

We append new indices:

- **13**: `I$ Tag Array Reads`
- **14**: `I$ Data Array Reads`
- **15**: `I$ Tag Array Writes`
- **16**: `I$ Data Array Writes`
- **17**: `I$ Evictions`
- **18**: `I$ Invalidation Tag Writes`

This requires `MHPMCounterNum` to be large enough for these indices to exist in the build.

## How to run (RR vs PLRU) in Simple System co-sim

The commands below follow the existing flow in [`doc/running_tests.md`](running_tests.md).

### 1) Build CoreMark

```bash
make -C ./examples/sw/benchmarks/coremark SUPPRESS_PCOUNT_DUMP=1
```

### 2) Build co-sim model for each policy

RR:

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-rr-proxy fusesoc_opts)
source ci/setup-cosim.sh
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS
```

PLRU:

```bash
IBEX_CONFIG_OPTS=$(./util/ibex_config.py maxperf-pmp-bmfull-icache-plru-proxy fusesoc_opts)
source ci/setup-cosim.sh
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system_cosim $IBEX_CONFIG_OPTS
```

### 3) Run CoreMark and save the CSVs

RR run:

```bash
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.rr.csv
mv ibex_simple_system.log ibex_simple_system.rr.log
```

PLRU run:

```bash
./ci/run-cosim-test.sh --skip-pass-check CoreMark examples/sw/benchmarks/coremark/coremark.elf
mv ibex_simple_system_pcount.csv ibex_simple_system_pcount.plru.csv
mv ibex_simple_system.log ibex_simple_system.plru.log
```

## Analysis: compute proxy energy and compare

Run the analysis script on both CSVs:

```bash
python3 util/icache_proxy_energy.py \
  --rr ibex_simple_system_pcount.rr.csv \
  --plru ibex_simple_system_pcount.plru.csv \
  --out-json icache_proxy_coremark.json
```

Expected outputs:

- `icache_proxy_coremark.json`: machine-readable per-run summary (raw counters + derived metrics)
- stdout: concise RR vs PLRU diff (cycles/instret/fetch-wait + proxy energy metrics)

## Optional: “LLM suggestion loop” (manual/offline)

This step is **not automated** and requires no API keys in-repo. The goal is to use an external LLM as a reasoning assistant after you have the structured JSON output.

### What to paste

Paste:

- the JSON file produced by the script (or the relevant subset: counters + derived metrics for RR and PLRU)
- the workload name and any run notes (e.g., tool versions, if the run was repeated)

### Prompt template

Copy/paste and fill in:

```text
We are optimizing the Ibex instruction cache replacement policy.

Context:
- Workload: <workload name>
- Config: <IBEX_CONFIG used>
- Two runs differ only by I$ victim policy: RR vs PLRU
- Proxy energy computed from counters:
  E = 1*TagReads + 2*DataReads + 2*TagWrites + 3*DataWrites + 1*Evictions + 1*InvalTagWrites

Here are the per-run JSON summaries (RR and PLRU):
<paste JSON here>

Tasks:
1) Decide which policy is better for this workload under this proxy metric, and why.
2) Identify which counters dominate E and which deltas matter most.
3) Suggest 2–3 next experiments to disambiguate: e.g., add a workload with larger I$ footprint, branch-heavy code, etc.
4) Do a sensitivity check: if we vary the weights (especially DataReads/DataWrites), does the recommendation change?

Constraints:
- Do not change functional behavior; only replacement policy and counter instrumentation are in scope.
- Prefer lightweight policies that do not add timing-critical logic.

Output format:
- Recommendation: RR or PLRU (with confidence)
- Evidence: bullets referencing the counters/deltas
- Next experiments: bullets
- Weight sensitivity: brief note
```

### How to interpret LLM suggestions

- Treat LLM output as **hypotheses** to validate via additional runs.\n+- Prefer suggestions that map directly to measurable counter changes (e.g., “reduce evictions” / “reduce tag reads”) rather than vague advice.\n+- If a suggestion implies changing the proxy weights, run the script with those weights to quantify sensitivity.
