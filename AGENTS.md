# Codex Project Instructions

This repository is a daily trading report pipeline. Use the detailed topical
rules in `.codex/rules/` as the source material for project-specific behavior.

## Architecture

The pipeline has three entry points that run in sequence through
`run_daily_morning.sh`:

1. `src.scripts.market` fetches global crypto market data from CoinGecko,
   formats a text summary, saves it, and sends it via Signal.
2. `src.scripts.net_pnl` loads daily trade CSV data, runs P&L analysis,
   generates a styled PNG table, saves CSV/text outputs, and sends them via
   Signal.
3. `src.scripts.trading_volume` loads trading volume data, checks volume
   against configured thresholds, generates a styled PNG table, saves CSV/PNG
   outputs, and sends them via Signal.

All entry points follow the same pattern: load data, analyze, save outputs, then
send via Signal. Signal failures are non-fatal and must be caught and logged
after files have been saved.

`src/settings.py` is the single source of truth for configuration. Prefer
`get_settings()` inside functions for testability; `app_settings` is acceptable
in entry-point scripts.

## Commands

Use `uv` for project commands:

```bash
uv run -m src.scripts.market
uv run -m src.scripts.net_pnl
uv run -m src.scripts.trading_volume
uv run market
uv run net_pnl
uv run trading_volume
uv run pytest
```

Run focused tests with `uv run pytest path/to/test.py` or
`uv run pytest path/to/test.py::test_name`.

## Coding Rules

- Make surgical edits and touch only the files required by the task.
- Preserve existing source column names, including special characters such as
  `npnl_r+un`, `volume_$`, and `npnl/volume_%`.
- Always use bracket notation for DataFrame columns with special characters.
- Use `df.loc[:, cols]` when selecting columns that must type as a DataFrame.
- Use `by=` as a keyword with `DataFrame.sort_values`.
- Add short comments only for non-obvious business logic, especially pandas
  transforms, aggregations, filters, and ratio calculations.
- Use existing helpers from `src.utils.dataframe` instead of reimplementing
  mapping, prefix extraction, ratio calculation, aggregation, or threshold
  filtering.
- Import `SignalClient` directly from `src.clients.signal`; do not use dynamic
  import loading.
- Configure logging with `logging.basicConfig()` only in entry-point `main()`
  functions. Utility modules should use `logging.getLogger(__name__)`.

## Data Contracts

Raw P&L CSV column order must match
`src/config/net_pnl.json -> analysis_data_columns`. Raw trading volume CSV
column order must match the trading volume config column list. If an upstream
CSV format changes, update the config before changing wrangling code.

P&L loss flags use the threshold from `src/config/net_pnl.json`, currently
`thresholds.loss_pnl`.

## Signal

Construct Signal clients with:

```python
from src.clients.signal import SignalClient

client = SignalClient()
```

Wrap sends in `try/except`, log failures with `exc_info=True`, and do not
re-raise send failures from report entry points.

## Testing

Signal integration tests skip automatically when `SIGNAL_TEST_SENDER` or
`SIGNAL_SENDER` is unset. Use `tmp_path` for temporary attachment files and keep
the Signal client fixture at module scope.

## Prefect

Prefect deployment rules live in `.codex/rules/prefect.md`. Deploy all flows
through `prefect.yaml` with:

```bash
uv run prefect --no-prompt deploy --all
```

Do not deploy individual flows by CLI unless explicitly requested.
