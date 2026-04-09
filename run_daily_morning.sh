#!/usr/bin/env bash
set -euo pipefail

cd /home/newuser1/work/new_project/training/reports

uv run -m src.scripts.daily.market
uv run -m src.scripts.daily.net_pnl
