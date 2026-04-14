# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands use `uv` as the runner. The package is installed in editable mode so `src.*` imports resolve correctly.

```bash
# Run a script directly
uv run -m src.scripts.daily.market
uv run -m src.scripts.daily.net_pnl
uv run -m src.scripts.daily.trading_volume

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

# Karpathy-Inspired Claude Code Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
