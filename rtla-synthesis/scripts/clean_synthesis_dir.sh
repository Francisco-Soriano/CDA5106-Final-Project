#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <target_dir> [--dry-run]"
  exit 1
fi

DIR="$(realpath -m "$1")"
DRY_RUN="${2:-}"

# Safety checks
if [[ ! -d "$DIR" ]]; then
  echo "Error: '$DIR' is not a directory"
  exit 1
fi
if [[ "$DIR" == "/" || "$DIR" == "" ]]; then
  echo "Refusing to operate on root or empty path"
  exit 1
fi

shopt -s nullglob dotglob
for path in "$DIR"/*; do
  base="${path##*/}"
  if [[ "$base" == "reports" ]]; then
    continue
  fi
  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo "[DRY-RUN] rm -rf -- \"$path\""
  else
    rm -rf -- "$path"
    echo "Removed: $path"
  fi
done