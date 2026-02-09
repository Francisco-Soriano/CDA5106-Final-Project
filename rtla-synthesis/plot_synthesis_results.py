import argparse
from typing import List, Tuple, Optional
import os
import json
import yaml
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

def filter_pareto_optimal_points(a: List[float], b: List[float]) -> Tuple[List[float], List[float]]:
    """
    Filters points to keep only Pareto optimal ones.
    A point is Pareto optimal if there is no other point that dominates it (i.e., no other point has better or equal values in both dimensions).
    For minimization problems, lower values are better.
    """
    if len(a) != len(b):
        raise ValueError("Lists a and b must have the same length")
    
    if not a:
        return [], []
    
    # Create list of (index, a_val, b_val) tuples
    points = list(enumerate(zip(a, b)))
    
    # Sort by a values (ascending), then by b values (ascending) for ties
    points.sort(key=lambda x: (x[1][0], x[1][1]))
    print(points)
    pareto_indices = []
    min_b = float('inf')
    
    for idx, (a_val, b_val) in points:
        # If this point has a better (lower) b value than any previous point
        if b_val < min_b:
            pareto_indices.append(idx)
            min_b = b_val
    
    # Extract Pareto optimal points
    pareto_a = [a[i] for i in pareto_indices]
    pareto_b = [b[i] for i in pareto_indices]
    
    return pareto_a, pareto_b

def plot_pareto(title: str, json_path: str, design_config_path: str, output_dir: str, power: bool = False, remove_points: bool = False, delay_y_axis: bool = False):
    """
    Plots Pareto curves for each design specified in design_config.
    By default, Y-axis is area/power based on the power flag, and the X-axis is delay.
    """
    def _median(values: List[float]) -> Optional[float]:
        if not values:
            return None
        s = sorted(values)
        n = len(s)
        m = n // 2
        if n % 2 == 1:
            return s[m]
        return 0.5 * (s[m - 1] + s[m])
    
    def interpolate_y_at_x(xs: List[float], ys: List[float], x_targets: List[float]) -> List[Optional[float]]:
        """Piecewise-linear interpolation of y(x). xs must be sortable; returns None if outside domain."""
        if not xs or not ys or len(xs) != len(ys):
            return [None for _ in x_targets]
        points = sorted(zip(xs, ys), key=lambda p: p[0])
        sx = [p[0] for p in points]
        sy = [p[1] for p in points]
        results: List[Optional[float]] = []
        for xt in x_targets:
            if xt < sx[0] or xt > sx[-1]:
                results.append(None)
                continue
            # Find interval
            y_val: Optional[float] = None
            for i in range(1, len(sx)):
                if sx[i-1] <= xt <= sx[i]:
                    x0, y0 = sx[i-1], sy[i-1]
                    x1, y1 = sx[i], sy[i]
                    if x1 == x0:
                        y_val = y0
                    else:
                        t = (xt - x0) / (x1 - x0)
                        y_val = y0 + t * (y1 - y0)
                    break
            results.append(y_val)
        return results
    
    def interpolate_x_at_y(xs: List[float], ys: List[float], y_targets: List[float]) -> List[Optional[float]]:
        """Piecewise-linear interpolation of x(y). ys must be sortable; returns None if outside domain."""
        if not xs or not ys or len(xs) != len(ys):
            return [None for _ in y_targets]
        points = sorted(zip(ys, xs), key=lambda p: p[0])
        sy = [p[0] for p in points]
        sx = [p[1] for p in points]
        results: List[Optional[float]] = []
        for yt in y_targets:
            if yt < sy[0] or yt > sy[-1]:
                results.append(None)
                continue
            x_val: Optional[float] = None
            for i in range(1, len(sy)):
                if sy[i-1] <= yt <= sy[i]:
                    y0, x0 = sy[i-1], sx[i-1]
                    y1, x1 = sy[i], sx[i]
                    if y1 == y0:
                        x_val = x0
                    else:
                        t = (yt - y0) / (y1 - y0)
                        x_val = x0 + t * (x1 - x0)
                    break
            results.append(x_val)
        return results
    
    def compute_savings(curve_base: dict, curve_cmp: dict, is_power: bool) -> None:
        """Compute and print max/avg X-saving at equal delay, and delay-saving at equal X."""
        x_label_name = "power" if is_power else "area"
        # Savings at equal delay (compare X)
        y_min = max(min(curve_base['y']), min(curve_cmp['y']))
        y_max = min(max(curve_base['y']), max(curve_cmp['y']))
        if y_max > y_min:
            num_samples = 200
            y_targets = [y_min + (y_max - y_min) * i / (num_samples - 1) for i in range(num_samples)]
            x_base = interpolate_x_at_y(curve_base['x'], curve_base['y'], y_targets)
            x_cmp = interpolate_x_at_y(curve_cmp['x'], curve_cmp['y'], y_targets)
            savings = []
            for xb, xc in zip(x_base, x_cmp):
                if xb is None or xc is None or xb == 0:
                    continue
                savings.append((xb - xc) / xb)
            if savings:
                max_sv = max(savings) * 100.0
                avg_sv = (sum(savings) / len(savings)) * 100.0
                med_sv = _median(savings)
                med_sv_pct = (med_sv * 100.0) if med_sv is not None else float('nan')
                print(f"[Equal delay] Max {x_label_name} saving: {max_sv:.2f}% | Avg {x_label_name} saving: {avg_sv:.2f}% | Median {x_label_name} saving: {med_sv_pct:.2f}% (N={len(savings)})")
        # Savings at equal X (compare delay)
        x_min = max(min(curve_base['x']), min(curve_cmp['x']))
        x_max = min(max(curve_base['x']), max(curve_cmp['x']))
        if x_max > x_min:
            num_samples = 200
            x_targets = [x_min + (x_max - x_min) * i / (num_samples - 1) for i in range(num_samples)]
            y_base = interpolate_y_at_x(curve_base['x'], curve_base['y'], x_targets)
            y_cmp = interpolate_y_at_x(curve_cmp['x'], curve_cmp['y'], x_targets)
            savings = []
            for yb, yc in zip(y_base, y_cmp):
                if yb is None or yc is None or yb == 0:
                    continue
                savings.append((yb - yc) / yb)
            if savings:
                max_sv = max(savings) * 100.0
                avg_sv = (sum(savings) / len(savings)) * 100.0
                med_sv = _median(savings)
                med_sv_pct = (med_sv * 100.0) if med_sv is not None else float('nan')
                print(f"[Equal {x_label_name}] Max delay saving: {max_sv:.2f}% | Avg delay saving: {avg_sv:.2f}% | Median delay saving: {med_sv_pct:.2f}% (N={len(savings)})")
    
    # Load design configuration
    with open(design_config_path, 'r') as f:
        config = yaml.safe_load(f)
    designs = config.get('designs', [])
    
    # Load Pareto data
    with open(json_path, 'r') as f:
        pareto_data = json.load(f)
    
    # Set up the plot
    plt.figure(figsize=(10, 8))
    
    # Define colors for different designs
    colors = plt.cm.Set1(np.linspace(0, 1, len(designs)))
    
    curves_data = []
    for i, design in enumerate(designs):
        if design not in pareto_data:
            print(f"Warning: Design {design} not found in Pareto data, skipping.")
            continue
        
        # Extract data for this design
        delays = []
        x_values = []
        
        for clock_period, data in pareto_data[design].items():
            timing = data['timing']
            if timing == "VIOLATED" or timing is None:
                continue
            
            delays.append(timing)
            
            if power:
                x_val = data['power']
            else:
                x_val = data['area']
            
            if x_val is not None:
                x_values.append(x_val)
            else:
                delays.pop()  # Remove the corresponding delay if x_val is None
        
        if not delays or not x_values:
            print(f"Warning: No valid data points for design {design}, skipping.")
            continue
        
        pareto_x, pareto_delays = filter_pareto_optimal_points(x_values, delays)
        # Plot non-Pareto optimal points as scatter
        non_pareto_x = [x for x in x_values if x not in pareto_x]
        non_pareto_delays = [d for d, x in zip(delays, x_values) if x not in pareto_x]
        if power:
            pareto_x = [x / 1e6 for x in pareto_x]
            non_pareto_x = [x / 1e6 for x in non_pareto_x]
            non_delay_label = 'Total Power (μW)'
        else:
            non_delay_label = 'Area (μm²)'
        if pareto_x:
            if delay_y_axis:
                # Area/power on X, delay on Y
                x_plot = pareto_x
                y_plot = pareto_delays
                non_pareto_x_plot = non_pareto_x
                non_pareto_y_plot = non_pareto_delays
                plt.xlabel(non_delay_label)
                plt.ylabel('Delay (ns)')
            else:
                # Default: delay on X, area/power on Y
                x_plot = pareto_delays
                y_plot = pareto_x
                non_pareto_x_plot = non_pareto_delays
                non_pareto_y_plot = non_pareto_x
                plt.ylabel(non_delay_label)
                plt.xlabel('Delay (ns)')
            
            plt.plot(x_plot, y_plot, 'o-', 
                    color=colors[i], linewidth=2, markersize=6,
                    label=f'{design}')
            curves_data.append({
                'label': design,
                'x': list(x_plot),
                'y': list(y_plot),
            })
            
            if non_pareto_x_plot and not remove_points:
                plt.scatter(non_pareto_x_plot, non_pareto_y_plot, 
                            color=colors[i], alpha=0.3, s=30)
    
    if power:
        plot_title = title + "\n(Switching Power + Internal Power + Leakage Power)"
    else:
        plot_title = title
        
    plt.title(plot_title)
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Save the plot
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{title}.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Pareto plot saved to {output_path}")

def create_pareto_json(input_dir: str, design_config_path: str, output_dir: str):
    """
    Creates a pareto_data.json file in output_dir, containing synthesis results for each design and clock period.
    Clock periods are sorted by their timing values rather than directory names.
    """
    # Load design names from YAML config
    with open(design_config_path, 'r') as f:
        config = yaml.safe_load(f)
    designs = config.get('designs', [])

    pareto_data = {}
    for design in designs:
        design_dir = os.path.join(input_dir, design)
        

        reports_dir = os.path.join(design_dir, 'reports')
        if not os.path.isdir(reports_dir):
            print(f"Reports directory not found for design {design} at {reports_dir}, skipping.")
            continue
        clock_period_data = {}
        for clock_period in os.listdir(reports_dir):
            clock_dir = os.path.join(reports_dir, clock_period)
            if not os.path.isdir(clock_dir):
                print(f"Clock period directory {clock_period} not found for design {design}, skipping.")
                continue
            timing_path = os.path.join(clock_dir, 'timing.rpt')
            area_path = os.path.join(clock_dir, 'area.rpt')
            power_path = os.path.join(clock_dir, 'power.rpt')
            timing = parse_timing_report(timing_path) if os.path.isfile(timing_path) else None
            area = parse_area_report(area_path) if os.path.isfile(area_path) else None
            power = parse_power_report(power_path, 'Total Power') if os.path.isfile(power_path) else None
            clock_period_data[clock_period] = {
                'timing': round(timing, 4) if timing is not None else "VIOLATED",
                'area': area,
                'power': power
            }
        def get_timing_value_for_sorting(clock_period):
            timing_data = clock_period_data[clock_period]['timing']
            if timing_data == "VIOLATED" or timing_data is None:
                return float('inf')
            return timing_data
        sorted_clock_periods = sorted(clock_period_data.keys(), key=get_timing_value_for_sorting)
        pareto_data[design] = {}
        for clock_period in sorted_clock_periods:
            pareto_data[design][clock_period] = clock_period_data[clock_period]
    
    # Write to JSON file
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'pareto_data.json')
    with open(output_path, 'w') as f:
        json.dump(pareto_data, f, indent=2)

def parse_timing_report(report_path: str) -> Optional[float]:
    """
    Extracts the 'data arrival time' value from the timing report.
    If 'VIOLATED' is found anywhere in the report, returns None.
    """
    # First pass: check for VIOLATED
    with open(report_path, 'r') as f:
        content = f.read()
        if 'VIOLATED' in content:
            return None
    
    # Second pass: extract data arrival time
    with open(report_path, 'r') as f:
        for line in f:
            if 'data arrival time' in line:
                # Extract the numeric value from the line
                parts = line.strip().split()
                if len(parts) >= 1:
                    try:
                        arrival_time = float(parts[-1])
                        return arrival_time
                    except ValueError:
                        print(f"Could not convert '{parts[-1]}' to float.")
                        return None
    return None

def parse_area_report(report_path: str) -> Optional[float]:
    """
    Extracts the value after 'Combinational area:' from the area report.
    Returns the value as a float, or None if not found.
    """
    with open(report_path, 'r') as f:
        for line in f:
            if 'Combinational area:' in line:
                parts = line.strip().split()
                # The value should be the last part of the line
                try:
                    return float(parts[-1])
                except ValueError:
                    return None
    return None

def parse_power_report(report_path: str, power_metric: str = 'Total Power') -> Optional[float]:
    """
    Extracts the value after 'Total Power =' from the power report.
    Returns the value as a float, or None if not found.
    """
    with open(report_path, 'r') as f:
        for line in f:
            if power_metric in line and '=' in line:
                parts = line.strip().split('=')
                if len(parts) >= 2:
                    value_str = parts[1].strip().split()[0]
                    try:
                        return float(value_str)
                    except ValueError:
                        return None
    return None

def main():
    parser = argparse.ArgumentParser(description="Plot synthesis results and Pareto curves.")
    parser.add_argument('--input_dir', '-i', required=True, help='Path to directory containing synthesis results for different designs')
    parser.add_argument('--design_config', '-d', required=True, help='Path to YAML config file with different designs to be plotted')
    parser.add_argument('--output_dir', '-o', required=True, help='Path to output directory where plots will be saved')
    parser.add_argument('--remove_points', '-r', action='store_true', help='Remove non-pareto optimal points from graph')
    parser.add_argument('--title', '-t', required=True, help='Title of the plot')
    parser.add_argument('--delay_y_axis', '-y', action='store_true', help='Plot delay on Y-axis instead of X-axis')
    args = parser.parse_args()

    # Create Pareto JSON data
    create_pareto_json(args.input_dir, args.design_config, args.output_dir)
    
    # Generate Pareto plots
    json_path = os.path.join(args.output_dir, 'pareto_data.json')
    
    print(f"Plotting area-delay curve")
    plot_pareto(
        title=f"Area-Delay Curves for {args.title}",
        json_path=json_path,
        design_config_path=args.design_config,
        output_dir=args.output_dir,
        power=False,
        remove_points=args.remove_points,
        delay_y_axis=args.delay_y_axis
    )
    
    print(f"Plotting power-delay curve")
    plot_pareto(
        title=f"Power-Delay Curves for {args.title}",
        json_path=json_path,
        design_config_path=args.design_config,
        output_dir=args.output_dir,
        power=True,
        remove_points=args.remove_points,
        delay_y_axis=args.delay_y_axis
    )

if __name__ == "__main__":
    main()
