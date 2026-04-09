#!/usr/bin/env bash
set -euo pipefail

cd /home/newuser1/work/new_project/training/reports

/home/newuser1/.local/bin/uv run -m src.scripts.daily.market
/home/newuser1/.local/bin/uv run -m src.scripts.daily.net_pnl
