#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Single-root mode: LifePlanner keeps its writable state inside this folder.
export LIFEPLANNER_PORTABLE=1
export LIFEPLANNER_DATA_DIR="$PWD/data"
export PIP_CACHE_DIR="$PWD/data/cache/pip"
export XDG_CACHE_HOME="$PWD/data/cache/xdg"
export XDG_CONFIG_HOME="$PWD/data/xdg/config"
export XDG_DATA_HOME="$PWD/data/xdg/share"
export PYTHONPYCACHEPREFIX="$PWD/data/cache/pycache"
mkdir -p "$PIP_CACHE_DIR" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$PYTHONPYCACHEPREFIX"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python main.py
