# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands use `uv` as the runner. The package is installed in editable mode so `src.*` imports resolve correctly.

```bash
# Run a script directly
uv run -m src.scripts.daily.market
uv run -m src.scripts.daily.net_pnl

# Or via CLI entry points (after install)
uv run market
uv run net_pnl

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_signal_client.py

# Run a single test
uv run pytest tests/test_signal_client.py::test_send_text_message_to_recipient
```

Signal integration tests require a live signal-cli REST API and will skip automatically if `SIGNAL_SENDER` is not set.

## Architecture

This is a **daily trading report pipeline** with two entry points that run in sequence via `run_daily_morning.sh` (triggered by a systemd timer at 04:20 UTC):

1. **`market.py`** — fetches global crypto market data from CoinGecko, formats a text summary, saves it, and sends it via Signal.
2. **`net_pnl.py`** — loads a daily CSV of trade data, runs P&L analysis, generates a styled PNG table, saves a CSV + text report, and sends them via Signal.

### Data flow for `net_pnl`

```
CSV file (data/)
  → load_data.load_local_data()
  → wrangle.wrangle_data()          # normalise columns, map symbols, extract base_strategy
  → dataframe.*                     # aggregate, filter, calculate ratios
  → format_message.build_daily_report()
  → save_data.{save_report, save_csv}
  → visualization.dataframe_to_png_styled()
  → SignalClient.send()
```

### Key design decisions

- **`src/settings.py`** is the single source of truth for all configuration. It uses Pydantic `BaseSettings` with `@lru_cache`, so `get_settings()` is safe to call anywhere — all modules import from it directly. Settings map 1:1 to `.env` variables (see `.env.example`).

- **`src/config.json`** holds business logic that changes rarely: symbol normalisation map, strategy name/category mappings, column lists, and the loss threshold. It is loaded once at import time via `src/utils/constants.py`.

- **Column names with special characters** (`npnl_r+un`, `volume_$`, `npnl/volume_%`) come from the raw CSV and are intentionally preserved to match the source data. Always use bracket notation (`df["npnl_r+un"]`), never attribute notation.

- **`wrangle_data()`** expects the raw CSV columns to be in the exact order defined in `config.json → analysis_data_columns`. If the upstream CSV format changes, update that list first.

- **Signal client loading**: `src/clients/signal.py` is a standard module — import it directly (`from src.clients.signal import SignalClient`). Do not use `importlib` dynamic loading.

- **Logging**: utility modules use `logger = logging.getLogger(__name__)` only. `logging.basicConfig()` is called exclusively inside `main()` in the two entry-point scripts, using `app_settings.log_level`.

- **Signal failures are non-fatal**: the `try/except` around `SignalClient.send()` in both entry points logs the error and continues, so a network issue never prevents report files from being saved.

## Code Conventions

- **Comments for complex logic**: Any line performing business logic that isn't immediately obvious (pandas transforms, aggregations, conditional filtering, ratio calculations) should have a short inline comment explaining the "why" or the intended result. Example:
  ```python
  # Calculate P&L per unit volume (scaled to percentage)
  return calculate_ratio_column(summary_df, "npnl_r+un", "volume_$", "npnl/volume_%", scale=100)
  ```
  This helps future readers (and future Claude instances) understand the intent without diving into function definitions.

- **Git commits**: When committing changes, do NOT include `Co-Authored-By:` trailers in the commit message. Write a clear, concise commit message (imperative mood, under 70 characters in the subject line) and let `git` handle attribution naturally.

## Scheduler

The systemd timer calls `run_daily_morning.sh`, which runs `market` then `net_pnl`. Logs go to `logs/daily_morning.log`. See `README.md` for full systemd setup and control commands.
