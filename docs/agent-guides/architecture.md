# Architecture

This is a **daily trading report pipeline** with three entry points that run in sequence via `run_daily_morning.sh` (triggered by a systemd timer at 04:20 UTC):

1. **`market.py`** — fetches global crypto market data from CoinGecko, formats a text summary, saves it, and sends it via Signal.
2. **`net_pnl.py`** — loads a daily CSV of trade data, runs P&L analysis, generates a styled PNG table, saves a CSV + text report, and sends them via Signal.
3. **`trading_volume.py`** — loads trading volume data, analyzes volume against requirement thresholds for monitored symbols, generates a styled PNG table with summary metrics, saves CSV + PNG, and sends via Signal.

All three scripts follow the same pattern: load data → analyze → save outputs → send via Signal (with signal failures as non-fatal). The wrapper script (`run_daily_morning.sh`) orchestrates the sequence.

## Data flow for `net_pnl`

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

## Key design decisions

- **`src/settings.py`** is the single source of truth for all configuration. It uses Pydantic `BaseSettings` with `@lru_cache`, so `get_settings()` is safe to call anywhere — all modules import from it directly. Settings map 1:1 to `.env` variables (located at `reports/.env`; see `.env.example` for reference).

- **Config files** are stored in `src/config/`:
  - **`net_pnl.json`** — Symbol normalization, strategy name/category mappings, column lists (analysis_data_columns, final_columns), and loss thresholds.
  - **`trading_volume.json`** — Monitored symbols, requirement volumes by exchange/product type, and column lists.
  - Both are loaded once at import time via `src/utils/constants.py` and exposed as module-level constants.

- **Column names with special characters** (`npnl_r+un`, `volume_$`, `npnl/volume_%`) come from the raw CSV and are intentionally preserved to match the source data. Always use bracket notation (`df["npnl_r+un"]`), never attribute notation.

- **`wrangle_data()`** expects the raw CSV columns to be in the exact order defined in `config.json → analysis_data_columns`. If the upstream CSV format changes, update that list first.

- **Signal client loading**: `src/clients/signal.py` is a standard module — import it directly (`from src.clients.signal import SignalClient`). Do not use `importlib` dynamic loading.

- **Logging**: utility modules use `logger = logging.getLogger(__name__)` only. `logging.basicConfig()` is called exclusively inside `main()` in the two entry-point scripts, using `app_settings.log_level`.

- **Signal failures are non-fatal**: the `try/except` around `SignalClient.send()` in all entry points logs the error and continues, so a network issue never prevents report files from being saved.

- **`app_settings` vs `get_settings()`**: `app_settings` is a module-level singleton (`app_settings = get_settings()` at the bottom of `settings.py`). Both are equivalent at runtime due to `@lru_cache`. Prefer `get_settings()` called inside functions for testability; `app_settings` is acceptable in entry-point scripts.
