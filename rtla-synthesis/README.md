# RTL Synthesis Environments

A repo containing synthesis environments configured for Synopsys RTL Architect (RTLA) for ASIC synthesis. Created for the purpose of pareto curve analysis.

## Prerequisites

### Software Requirements
- `Synopsys RTL Architect` (RTLA)
- `Python 3.7+`
- `Synopsys PrimePower` (For power analysis)
- `tmux` for launching synthesis runs in persistent terminal sessions

- matplotlib
- yaml

### System Requirements
- Linux environment
- X11 forwarding capability (for GUI tools)

## Directory Structure

```
rtla-synthesis/
├── asic-synthesis-base/                # Base synthesis environment (copy for each design)
│   ├── data/
│   │   ├── constraints/               # Design constraints, corners, and scenario data
│   │   ├── ndm/                       # Technology files for 32nm PDK
│   │   └── rtl/                       # RTL design files (user-provided)
│   ├── scripts/
│   │   ├── clean_dir.sh               # Remove RTLA files and metadata (clears reports)
│   │   ├── run_synthesis.tcl          # Analyzes, elaborates RTL, and performs physical-aware synthesis
│   │   └── setup.tcl                  # Creates design library and loads technology files
│   └── pareto_synthesis.tcl           # Pareto curve synthesis script
├── fpga-synthesis-base/                # Base synthesis environment (copy for each design)
├── design_config.yaml                 # List of designs for batch synthesis
├── plot_asic_results.py               # Plot Pareto curves from ASIC synthesis results
├── plot_fpga_results.py               # Plot Pareto curves from FPGA synthesis results
└── README.md                          # This file
```

## Usage

### ASIC Synthesis of a Single Design

For each design to be evaluated, create a renamed copy of `asic-synthesis-base/` under the same top-level directory

Copy the RTL files of the design into `data/rtl` inside of the newly-copied directory. It is important that the top module name matches the name of the file in which it is located

Navigate inside the copied directory and run

`rtl_shell -f pareto_synthesis.tcl -x "set DESIGN_NAME <top module name>"`

This will launch the RTL Architect tool and begin pareto curve generation. The script will exit RTLA automatically once complete.

**Note**: By default, this script is configured to read in SystemVerilog files. Change line 18 of `scripts/run_synthesis.tcl` if you are synthesizing Verilog or VHDL files

**Note**: Synthesis runs may take some time to complete. To run RTLA in a persistent terminal in case the SSH session gets disconnected, use the `tmux` command. 

`tmux new -s <session name>`

### Batch Synthesis

Scripts are provided to launch multiple parallel synthesis runs for different designs automatically, each in its own tmux session. 

#### Workflow

1. **Configure designs** — Create a file `design_config.yaml` to list the designs to synthesize:

```yaml
designs:
  - design_1
  - design_2
  - design_3
```

2. **Create synthesis directories** — Run `setup_synthesis_dirs.py` to copy the base synthesis environment for each design:

```bash
python scripts/setup_synthesis_dirs.py \
  -o ./synthesis_output \
  -s ./asic-synthesis-base \
  -d design_config.yaml
```

This creates `synthesis_output/design_1/`, `synthesis_output/design_2/`, etc., each containing the synthesis scripts and directory structure.

3. **Add RTL** — Copy the RTL files for each design into `synthesis_output/<design>/data/rtl/`. The top module name must match the design name in the config.

4. **Run batch synthesis** — Launch synthesis for all designs in parallel tmux sessions:

```bash
./scripts/batch_run_synthesis.sh design_config.yaml -o ./synthesis_output
```

Each design runs in a separate tmux session named after the design (e.g. `adder_rca_64b`). To attach and monitor progress:

```bash
tmux attach -t <design name>
```

To detach from a session without stopping it: `Ctrl+b` then `d`.

5. **Plot results** — After synthesis completes, generate Pareto curves:

```bash
python plot_asic_results.py \
  -i ./synthesis_output \
  -d design_config.yaml \
  -o ./plots \
  -t "Adder Pareto Curves"
```

#### Cleaning Between Runs

To remove synthesis artifacts (while keeping reports) before re-running:

```bash
./scripts/clean_synthesis_dir.sh ./synthesis_output/adder_rca_64b
```

## Configuration

### Synthesis Configuration

The synthesis environment is configured for the following four design corners:

1. **FF1p16125c**: Short path delay, highest leakage current
2. **FF1p1640c**: Shortest path delays, worst-case for hold timing, higher switching power, lower leakage
3. **SS0p95v125c**: Longest path delays, worst-case for setup timing, higher leakage
4. **SS0p95v40c**: Long path delays, low leakage

As this environment is designed for **evaluating** and **comparing** different RTLs, with less of a focus on physical implementation/manufacturability, only the **ss0p95v125c** corner is currently being evaluated to speed up synthesis time.

## Pareto Curve Generation

The script `pareto_synthesis.tcl` contains the logic for generating a pareto curve for a given design. It uses the following procedure for curve generation:

1. Find the minimum achievable area by setting a loose timing constraint (5.00ns by default). 
2. Find this midpoint of this loose timing constraint with an extremely tight timing constraint (0.01ns by default).
3. Evaluate the midpoint and check to see if the area has increased. If so, treat the midpoint constraint as the new lower bound. If the area has not changed, treat the midpoint constraint as the new upper bound. 
4. Repeat the process for a fixed number of iterations or until the difference between the high and low timing constraints is sufficiently small. This final constraint will be the constraint producing the minimum area design.
5. Repeat the same binary search process as above, this time finding the minimum delay timing constraint. This will be the timing constraint with slack=0.
6. With the extreme timing constraints found, compute a list of delay constraints to evaluate based on the `num_pareto_points` variable
7. Evaluate this list of constraints, generating reports for each point on the pareto curve.
6. Exit after completing pareto curve generation

### Generated Reports

- `area.rpt`
- `power.rpts`
- `qor.rpt`
- `resources.rpts`
- `timing.rpt` 

## Pareto Curve Plotting

The `plot_asic_results.py` script generates Pareto curves from synthesis results. This tool visualizes the trade-offs between area, delay, and power for different designs.

### Design Configuration File

The `design_config.yaml` file should contain the directory names for the different designs to be plotted. Example structure:

```yaml
designs:
  - adder_brent_kung_64b
  - adder_sklansky_64b
  - adder_ripple_carry_64b
```

### Usage

```bash
python plot_asic_results.py [OPTIONS]
```

### Required Arguments

| Argument | Short | Description |
|----------|-------|-------------|
| `--input_dir` | `-i` | Path to directory containing synthesis results for different designs |
| `--design_config` | `-d` | Path to YAML config file with different designs to be plotted |
| `--output_dir` | `-o` | Path to output directory where plots will be saved |
| `--title` | `-t` | Title of the plot |

### Optional Arguments

| Argument | Short | Description |
|----------|-------|-------------|
| `--remove_points` | `-r` | Remove non-Pareto optimal points from graph |
| `--delay_y_axis` | `-y` | Plot delay on the y axis instead of the x axis |

### Example Usage

#### Basic Pareto Curve Generation
```bash
python plot_asic_results.py \
    -i ./synthesis_output \
    -d design_config.yaml \
    -o ./plots \
    -t "Brent-Kung 64-bit Adder Pareto Curve"
```

#### Clean Pareto Curve (Optimal Points Only)
```bash
python plot_asic_results.py \
    -i ./synthesis_output \
    -d design_config.yaml \
    -o ./plots \
    -t "Brent-Kung 64-bit Adder Pareto Curve Optimal Points" \
    -r
```

### Output

The script generates:
- **Pareto curve plots** showing Area vs Delay or Power vs Delay tradeoffs
- **JSON data file** containing raw extracted metrics
