# Reports Scheduler

Daily trading report pipeline that fetches market data, calculates P&L, and analyzes trading volume — then sends results via Signal.

## Prerequisites

### 1. Signal (signal-cli REST API)

```bash
docker run -d \
  --name signal-cli \
  -p 8081:8080 \
  bbernhard/signal-cli-rest-api
```

Register your number following the [signal-cli-rest-api docs](https://github.com/bbernhard/signal-cli-rest-api). Set `SIGNAL_BASE_URL`, `SIGNAL_SENDER`, and `SIGNAL_RECIPIENT` or `SIGNAL_GROUP_ID` in `.env`.

### 2. Prefect database

By default, Prefect uses SQLite under `PREFECT_HOME`. For PostgreSQL, set
`PREFECT_API_DATABASE_CONNECTION_URL` in `.env` (see `.env.example`).

## Quickstart

```bash
cp .env.example .env   # fill in required values
./prefect.sh           # fresh start: kill old processes, start server + deploy + worker
```

UI available at `http://localhost:4200`.

## Scripts

| Script | What it does |
|--------|-------------|
| `uv run market` | Fetches CoinGecko global market data, sends text summary via Signal |
| `uv run net_pnl` | Loads trade CSV, runs P&L analysis, sends PNG table + text via Signal |
| `uv run trading_volume` | Loads volume CSV, checks against thresholds, sends PNG table via Signal |
| `uv run new_listing <symbol>` | Runs `src/config/new_listing/<symbol>.json` through the new-listing setup flow |
| `uv run strategy_fills <symbol>` | Fetches volume strategy fills/status with `base_currency`/`quote_currency` |
| `uv run arb_param_analysis ...` | Uses public Binance/KuCoin data to recommend simple arbitrage size/sleep params |

Manual RCJ ops workflows are also available in Prefect UI on dedicated work
pools. See `docs/prefect_ops.md` for balance/transfer/monitor playbook tasks,
new listing, volatility, volume, stacker, mirror control, and diagnostics
deployments. Configure their default API route with the `RCJ_OPS_*` values in
`.env`.

For simple arbitrage parameter analysis, see `docs/arb_param_analysis.md`.

Run all three in sequence:

```bash
uv run -m src.scripts.market
uv run -m src.scripts.net_pnl
uv run -m src.scripts.trading_volume
```

New-listing configs live under `src/config/new_listing/`. Most runs only need
the symbol config name:

```bash
uv run new_listing testing --dry-run
uv run new_listing KAIO
uv run new_listing --config src/config/new_listing/custom.json
```

## Prefect orchestration

`prefect.sh` manages the local Prefect server, deployments, and worker:

```bash
./prefect.sh           # fresh start: kill old, start server + deploy + worker
./prefect.sh stop      # gracefully stop server and worker
./prefect.sh start     # restart stopped server and worker (no redeploy)
./prefect.sh redeploy  # redeploy flows on running server + restart worker
```

Flows are defined in `prefect.yaml`. The `daily-morning` deployment runs all three flows in parallel on a cron schedule (`30 1 * * *` UTC). The other three deployments (`market`, `net-pnl`, `trading-volume`) are manual-trigger only.

Logs: `logs/prefect/`. Runtime PID files: `logs/pid/`.

## Environment

Copy `.env.example` to `.env` and fill in:

- `COINGECKO_API_KEY`
- `SIGNAL_SENDER`, `SIGNAL_RECIPIENT` or `SIGNAL_GROUP_ID`, `SIGNAL_BASE_URL`
- `NET_PNL_INPUT_PATH`, `TRADING_VOLUME_INPUT_PATH` (default: `data/trades.csv`, `data/trading_volume.csv`)
- `PREFECT_API_URL`, `PREFECT_LOG_DIR`, `PREFECT_PID_DIR`, `PREFECT_WORK_POOLS`
- `RCJ_OPS_BASE_ENDPOINT`, `RCJ_OPS_TIMEOUT_SECONDS`, `RCJ_OPS_EXECUTION_MODE`, `RCJ_OPS_SSH_HOST`

## Tests

```bash
uv run pytest
```

Signal integration tests skip automatically if `SIGNAL_SENDER` is not set in `.env`.
