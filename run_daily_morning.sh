#!/usr/bin/env bash
set -euo pipefail

cd /home/newuser1/work/new_project/training/reports

uv run -m src.scripts.market
uv run -m src.scripts.net_pnl
uv run -m src.scripts.trading_volume
