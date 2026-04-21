# Reports Scheduler

Daily trading report pipeline that fetches market data, calculates P&L, and analyzes trading volume — then sends results via Signal.

## Quickstart

```bash
cp .env.example .env   # fill in required values
./start.sh             # start Prefect server + deploy flows + start worker
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

`start.sh` manages the local Prefect server, deployments, and worker:

```bash
./start.sh            # fresh start
./start.sh redeploy   # redeploy flows + restart worker after code/env changes
```

Flows are defined in `prefect.yaml`. The `daily-morning` deployment runs all three flows in parallel on a cron schedule (`30 1 * * *` UTC = 09:30 local). The other three deployments (`market`, `net-pnl`, `trading-volume`) are manual-trigger only.

To stop everything:

```bash
pkill -f "prefect server start" 2>/dev/null || true
pkill -f "prefect worker start" 2>/dev/null || true
```

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
