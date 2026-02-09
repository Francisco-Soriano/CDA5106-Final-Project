#!/usr/bin/env bash
# Batch run synthesis for multiple designs in parallel tmux sessions
# Usage: ./batch_run_synthesis.sh <design config name>.yaml -o ./path/to/synthesis/output/dir

set -e

usage() {
    echo "Usage: $0 <yaml_file> -o <output_path>"
    echo "  Starts a tmux session for each design, running synthesis in its directory."
    exit 1
}

if [[ $# -lt 3 ]]; then
    usage
fi

YAML_FILE="$1"
shift

OUTPUT_PATH=""
while getopts "o:" opt; do
    case $opt in
        o) OUTPUT_PATH="$OPTARG" ;;
        *) usage ;;
    esac
done

if [[ -z "$OUTPUT_PATH" ]]; then
    echo "Error: -o output_path is required"
    usage
fi

if [[ ! -f "$YAML_FILE" ]]; then
    echo "Error: YAML file not found: $YAML_FILE"
    exit 1
fi

if [[ ! -d "$OUTPUT_PATH" ]]; then
    echo "Error: Output path not found: $OUTPUT_PATH"
    exit 1
fi

python3 - "$YAML_FILE" << 'PYTHON_SCRIPT' | while IFS= read -r DESIGN; do
import sys
import yaml

with open(sys.argv[1]) as f:
    config = yaml.safe_load(f)
for d in config.get('designs', []):
    print(d)
PYTHON_SCRIPT
    DESIGN_DIR="$OUTPUT_PATH/$DESIGN"
    if [[ ! -d "$DESIGN_DIR" ]]; then
        echo "Skipping '$DESIGN': directory not found at $DESIGN_DIR"
        continue
    fi

    if tmux has-session -t "$DESIGN" 2>/dev/null; then
        echo "Skipping '$DESIGN': tmux session already exists"
        continue
    fi

    DESIGN_DIR_ABS=$(cd "$DESIGN_DIR" && pwd)
    tmux new-session -d -s "$DESIGN" -c "$DESIGN_DIR_ABS"
    tmux send-keys -t "$DESIGN" "rtl_shell -f pareto_synthesis.tcl -x \"set DESIGN_NAME $DESIGN\"" Enter
    echo "Started tmux session '$DESIGN' for synthesis"
done
