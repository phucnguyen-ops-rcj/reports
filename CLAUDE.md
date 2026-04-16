# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands use `uv` as the runner. The package is installed in editable mode so `src.*` imports resolve correctly.

```bash
# Run a script directly
uv run -m src.scripts.net_pnl
uv run -m src.scripts.market
uv run -m src.scripts.trading_volume

# Or via CLI entry points (after install)
uv run market
uv run net_pnl
uv run trading_volume

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_signal_client.py

# Run a single test
uv run pytest tests/test_signal_client.py::test_send_text_message_to_recipient
```

Signal integration tests require a live signal-cli REST API and will skip automatically if `SIGNAL_SENDER` is not set.

## Architecture

This is a **daily trading report pipeline** with three entry points that run in sequence via `run_daily_morning.sh` (triggered by a systemd timer at 04:20 UTC):

1. **`market.py`** — fetches global crypto market data from CoinGecko, formats a text summary, saves it, and sends it via Signal.
2. **`net_pnl.py`** — loads a daily CSV of trade data, runs P&L analysis, generates a styled PNG table, saves a CSV + text report, and sends them via Signal.
3. **`trading_volume.py`** — loads trading volume data, analyzes volume against requirement thresholds for monitored symbols, generates a styled PNG table with summary metrics, saves CSV + PNG, and sends via Signal.

All three scripts follow the same pattern: load data → analyze → save outputs → send via Signal (with signal failures as non-fatal). The wrapper script (`run_daily_morning.sh`) orchestrates the sequence.

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

## Type Checking (Pyrefly)

Pyrefly is the active type checker (configured via `[tool.pyrefly]` in `pyproject.toml` with `search-path = ["."]`). Known patterns to follow:

- **`df[list_of_cols]`** is typed as `DataFrame | Series` by pandas stubs — use `df.loc[:, cols]` to get an unambiguous `DataFrame`.
- **`DataFrame.sort_values`** requires `by=` as a keyword argument, not positional, for Pyrefly to resolve the correct overload.
- **`_to_float()` returns `float | None`** — use `(value or 0.0)` before arithmetic to narrow the type.
- **`datetime.now(tz)`** requires `tzinfo`, not `str` — use `ZoneInfo(app_settings.tz)` (stdlib, no stubs needed) instead of `pytz.timezone(app_settings.tz)`.
- **`pd.to_datetime("now") - Series`** — Pyrefly can't infer this returns `Series[Timedelta]`; suppress with `# pyrefly: ignore[missing-attribute]`.
- To silence a false positive inline: `# pyrefly: ignore[<error-code>]`

## Code Conventions

- **Comments for complex logic**: Any line performing business logic that isn't immediately obvious (pandas transforms, aggregations, conditional filtering, ratio calculations) should have a short inline comment explaining the "why" or the intended result. Example:
  ```python
  # Calculate P&L per unit volume (scaled to percentage)
  return calculate_ratio_column(summary_df, "npnl_r+un", "volume_$", "npnl/volume_%", scale=100)
  ```
  This helps future readers (and future Claude instances) understand the intent without diving into function definitions.

- **Git commits**: Write a clear, concise commit message (imperative mood, under 70 characters in the subject line). Let `git` handle attribution naturally.

## Scheduler

The systemd timer calls `run_daily_morning.sh`, which runs `market`, then `net_pnl`, then `trading_volume`. Logs go to `logs/daily_morning.log`. See `README.md` for full systemd setup and control commands.

---

## Coding Behaviour

- **Ask before assuming**: surface ambiguity and tradeoffs before implementing; if multiple interpretations exist, present them.
- **Minimum viable change**: no features, abstractions, or error handling beyond what was asked. If it could be 50 lines, don't write 200.
- **Surgical edits**: touch only what the task requires. Don't improve adjacent code, fix formatting, or remove pre-existing dead code. Remove imports/variables that *your* changes made unused.
- **Verify before closing**: every task should have a clear done-state (tests pass, script runs, error gone). State it upfront for multi-step work.
