# CDA5106-Final-Project
CORE: Cache Optimization and Reasoning Agent for Power Efficiency

# Abstract
Central Processing Units (CPUs) perform massive amounts of operations but waste significant energy moving data, even with caches. Existing cache optimization work mainly focuses on performance (miss rate, latency) rather than power. CORE is an RTL optimization framekwork that uses off-chip LLMs and performance counters (reads, writes, evictions) as power proxies to track and reduce cache energy. In an Ibex instruction-cache case study, only some AI-generated optimizations were valid, but a prefetch-throttling approach achieved a 14.2% energy reduction with minimal performance impact, highlighting both the high potential and remaining unreliability of LLM-driven RTL design - specifcially in terms of power.

## Repo Structure

```
CDA5106-Final-Project/
│── README.md
│── Makefile
│── run.sh
│── requirements.txt
│
├── scripts/
│   ├── icache_proxy_energy.py
│   ├── parse_pcount.py
│   └── utils.py
│
├── data/
│   ├── ibex_simple_system_pcount.csv
│   └── icache_proxy_coremark.json
│
├── results/
│   ├── baseline/
│   ├── optimization_1/
│   ├── optimization_2/
│   ├── optimization_3/
│   └── optimization_4/
│
├── ibex_edited/
│   ├── rtl/
│   │   └── ibex_icache.sv
│   └── configs/
│
└── docs/
    ├── report.md
    └── figures/
```

# Contact information
Jordan Merek - jo045021@ucf.edu

Alexander Garcia - al743857@ucf.edu

Julian Vasquez - ju081309@ucf.edu

Francisco Soriano - fr015568@ucf.edu
