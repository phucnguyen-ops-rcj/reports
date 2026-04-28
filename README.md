# Reports Scheduler

Daily trading report pipeline that fetches market data, calculates P&L, and analyzes trading volume — then sends results via Signal.

## Prerequisites

### 1. Signal (signal-cli REST API)

```bash
docker run -d \
  --name signal-cli \
  -p 8080:8080 \
  bbernhard/signal-cli-rest-api
```

Register your number following the [signal-cli-rest-api docs](https://github.com/bbernhard/signal-cli-rest-api). Set `SIGNAL_BASE_URL`, `SIGNAL_SENDER`, and `SIGNAL_RECIPIENT` or `SIGNAL_GROUP_ID` in `.env`.

### 2. PostgreSQL (Prefect database)

```bash
docker run -d \
  --name prefect-postgres \
  -e POSTGRES_USER=prefect \
  -e POSTGRES_PASSWORD=prefect \
  -e POSTGRES_DB=prefect \
  -p 5432:5432 \
  postgres:16
```

Set `PREFECT_SERVER_DATABASE_CONNECTION_URL` in `.env` (see `.env.example`).

## Quickstart

```bash
cp .env.example .env   # fill in required values
uv add asyncpg         # required for PostgreSQL async driver (first time only)
./prefect.sh           # fresh start: kill old processes, start server + deploy + worker
```

UI available at `http://localhost:4200`.

## Scripts

| Script | What it does |
|--------|-------------|
| `uv run market` | Fetches CoinGecko global market data, sends text summary via Signal |
| `uv run net_pnl` | Loads trade CSV, runs P&L analysis, sends PNG table + text via Signal |
| `uv run trading_volume` | Loads volume CSV, checks against thresholds, sends PNG table via Signal |

Run all three in sequence:

```bash
uv run -m src.scripts.market
uv run -m src.scripts.net_pnl
uv run -m src.scripts.trading_volume
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

Logs: `logs/prefect_server.log`, `logs/prefect_worker.log`.

## Environment

Copy `.env.example` to `.env` and fill in:

- `COINGECKO_API_KEY`
- `SIGNAL_SENDER`, `SIGNAL_RECIPIENT` or `SIGNAL_GROUP_ID`, `SIGNAL_BASE_URL`
- `NET_PNL_INPUT_PATH`, `TRADING_VOLUME_INPUT_PATH` (default: `data/trades.csv`, `data/trading_volume.csv`)

## Tests

```bash
uv run pytest
```

Signal integration tests skip automatically if `SIGNAL_SENDER` is not set in `.env`.
