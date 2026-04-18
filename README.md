# CDA5106-Final-Project
CORE: Cache Optimization and Reasoning Agent for Power Efficiency

# Abstract
Central Processing Units (CPUs) perform massive amounts of operations but waste significant energy moving data, even with caches. Existing cache optimization work mainly focuses on performance (miss rate, latency) rather than power. CORE is an RTL optimization framekwork that uses off-chip LLMs and performance counters (reads, writes, evictions) as power proxies to track and reduce cache energy. In an Ibex instruction-cache case study, only some AI-generated optimizations were valid, but a prefetch-throttling approach achieved a 14.2% energy reduction with minimal performance impact, highlighting both the high potential and remaining unreliability of LLM-driven RTL design - specifcially in terms of power.

# Repo structure
CDA5106-Final-Project/
│
├── README.md
├── LICENSE
│
├── ibex_edited/
│   ├── (modified RTL files, e.g., ibex_icache.sv)
│   └── (other Ibex-related source files)
│
├── util/
│   ├── icache_proxy_energy.py
│   ├── (scripts for analysis / power proxy)
│
├── results/
│   ├── ibex_simple_system_pcount.csv
│   ├── icache_proxy_coremark.json
│   └── (experiment outputs / metrics)
│
├── reports/
│   ├── final_report.pdf
│   └── (writeups, figures, explanations)
│
├── scripts/
│   ├── run_experiments.sh
│   └── (automation / simulation scripts)
│
└── docs/
    └── (images, diagrams, supporting material)

# Contact information
Jordan Merek - jo045021@ucf.edu
Alexander Garcia - al743857@ucf.edu
Julian Vasquez - ju081309@ucf.edu
Francisco Soriano - fr015568@ucf.edu
