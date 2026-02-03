# Low-Power Cache Architecture Using RTL Translation of Open-Source Cache Simulators

## Project Overview
This project executes **low-power cache design techniques** by starting from an **open-source cache simulator baseline** and translating it into a **parameterized RTL (Verilog) cache implementation**. Using this baseline, we implement and evaluate power-aware optimizations while preserving functional correctness while lowering power.

---

## Objectives
- Identify one or more **open-source cache simulators** written in C/C++.
- Translate the simulator architecture into a **parameterized Verilog RTL cache**.
- Implement a **baseline cache replacement policy** (e.g., LRU).
- Introduce **low-power optimizations** to the cache datapath and control logic.
- Quantitatively compare baseline and optimized designs using **power proxy metrics**. (Using OS tools, such as Yosys, OpenRoad, iVerilog, etc.)
- ~~Optionally evaluate how the same optimization behaves across **different cache architectures**.~~

---

## Project Scope
The cache is designed to be configurable and supports:
- Variable cache sizes
- Configurable line sizes
- Configurable associativity
- Standard cache behaviors (i.e hits, misses, evictions, & writebacks)

Power evaluation focuses on **activity-based proxies** rather than absolute power numbers.

---

## Architecture Overview

### Cache Datapath
- Tag array
- Data array
- Valid and dirty bits
- Hit/miss detection logic

### Control Logic
- Finite State Machine (FSM) for:
  - Cache misses
  - Line refills
  - Writebacks

### Replacement Policy
- **Baseline**: Least Recently Used (LRU) / FIFO
- **Optimized variants**: Power-aware modifications to reduce unnecessary activity

---

## Power Optimization Strategy
Power optimizations target reductions in:
- Unnecessary tag comparisons
- Redundant data array accesses
- Excessive LRU state updates
- Control logic toggling during non-critical events (e.g., writebacks)

Power impact is measured using proxy metrics such as:
- Number of tag array accesses
- Number of data array accesses
- LRU update events
- Read/write operations

Baseline metrics are compared against optimized implementations to quantify improvements.

---

## Verification and Evaluation
Verification is performed using Verilog testbenches that:
- Validate functional correctness
- Measure hit and miss rates
- Track evictions and writebacks
- Collect power proxy metrics

Results are compared between:
- Baseline cache implementation
- Power-optimized cache implementation(s)

---

## Tools and Technologies
- **iVerilog** – Verilog design & simulation
- **Yosys** - Verilog synthesis
- **OpenROAD** - P&R Tool
- **GitHub** – Version control and reference cache simulators
- **LaTeX** – Abstract, documentation and final report

---

## Repository Structure
├── rtl/ # Verilog cache implementation
├── tb/ # Testbenches
├── scripts/ # Simulation and analysis scripts
├── docs/ # Documentation and report material
└── README.md

---

## Stretch Goals
- Support for additional replacement policies
- Integration with power estimation tools
- ~~Cross-architecture comparison of power optimizations~~

---

## Authors
Jordan Merkel, Alexander Garcia, Julian Vazquez, Francisco Soriano

---

## References
- Open-source cache simulator repositories
- Academic literature on low-power cache design
- Open source tool documentation
