from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.clients.databases.redis import RedisClient, RedisConfig
from src.utils.constants import ANALYSIS_DATA_COLUMNS

PNL_METRICS = {
    "Buy",
    "Sell",
    "Trade",
    "Netpos",
    "NetRpnl",
    "NetUpnl",
    "RpnlWFees",
}


def parse_pnl_key(key: str) -> tuple[str, str, str, str] | None:
    parts = key.split(":")
    if len(parts) != 4:
        return None

    strategy, symbol, raw_market, metric = parts
    market = normalize_market(raw_market)
    if market is None or metric not in PNL_METRICS:
        return None
    return market, strategy, symbol, metric


def normalize_market(raw_market: str) -> str | None:
    normalized = raw_market.strip().lower()
    if normalized == "spot":
        return "spot"
    if normalized == "future":
        return "perp"
    return None


def group_metric_keys(keys: list[str]) -> dict[tuple[str, str, str], dict[str, str]]:
    grouped: dict[tuple[str, str, str], dict[str, str]] = defaultdict(dict)
    for key in keys:
        parsed = parse_pnl_key(key)
        if parsed is None:
            continue
        market, strategy, symbol, metric = parsed
        grouped[(market, strategy, symbol)][metric] = key
    return dict(grouped)


def sum_series_points(points: list[list[Any]]) -> float:
    return sum(float(point[1]) for point in points)


def last_series_value(points: list[list[Any]]) -> float:
    if not points:
        return 0.0
    return float(points[-1][1])


def build_output_row(
    market: str,
    strategy: str,
    symbol: str,
    metric_keys: dict[str, str],
    fetch_series: callable,
) -> dict[str, Any]:
    buy_sum = sum_series_points(fetch_series(metric_keys.get("Buy")))
    sell_sum = sum_series_points(fetch_series(metric_keys.get("Sell")))
    netpos_last = last_series_value(fetch_series(metric_keys.get("Netpos")))
    rpnl_last = last_series_value(fetch_series(metric_keys.get("NetRpnl")))
    unpnl_last = last_series_value(fetch_series(metric_keys.get("NetUpnl")))
    rpnlwfees_last = last_series_value(fetch_series(metric_keys.get("RpnlWFees")))
    trade_count = int(last_series_value(fetch_series(metric_keys.get("Trade"))))

    volume = buy_sum - sell_sum
    npnl = rpnl_last + unpnl_last
    npnl_ratio = 0.0 if volume == 0 else (npnl / volume) * 100

    return {
        "market": market,
        "strategy": strategy,
        "symbol": symbol,
        "volume_$": round(volume, 4),
        "net_position": round(netpos_last, 4),
        "net_position_$": round(netpos_last, 4),
        "rpnl": round(rpnl_last, 4),
        "unpnl": round(unpnl_last, 4),
        "rpnlwfees": round(rpnlwfees_last, 4),
        "npnl_r+un": round(npnl, 4),
        "npnl/volume_%": f"{npnl_ratio:.4f}%",
        "trade_count": trade_count,
    }


def build_rows_from_grouped_keys(
    grouped_keys: dict[tuple[str, str, str], dict[str, str]],
    fetch_series: callable,
) -> list[dict[str, Any]]:
    rows = [
        build_output_row(market, strategy, symbol, metric_keys, fetch_series)
        for (market, strategy, symbol), metric_keys in sorted(grouped_keys.items())
    ]
    return rows


def time_window_bounds(window_hours: int) -> tuple[int, int]:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=window_hours)
    return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)


def build_remote_export_script(
    connection: dict[str, Any],
    start_ms: int,
    end_ms: int,
) -> str:
    payload = {
        "connection": connection,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "metrics": sorted(PNL_METRICS),
        "columns": ANALYSIS_DATA_COLUMNS,
    }
    return f"""
import json
from collections import defaultdict
import redis

payload = json.loads({json.dumps(json.dumps(payload))})
client = redis.Redis(**payload["connection"])
metrics = set(payload["metrics"])
start_ms = payload["start_ms"]
end_ms = payload["end_ms"]

def normalize_market(raw_market):
    normalized = raw_market.strip().lower()
    if normalized == "spot":
        return "spot"
    if normalized == "future":
        return "perp"
    return None

grouped = defaultdict(dict)
for key in client.scan_iter(count=1000):
    parts = str(key).split(":")
    if len(parts) != 4:
        continue
    strategy, symbol, raw_market, metric = parts
    market = normalize_market(raw_market)
    if market is None or metric not in metrics:
        continue
    grouped[(market, strategy, symbol)][metric] = str(key)

def ts_range(key):
    if not key:
        return []
    return list(client.execute_command("TS.RANGE", key, start_ms, end_ms))

def sum_points(points):
    return sum(float(point[1]) for point in points)

def last_value(points):
    if not points:
        return 0.0
    return float(points[-1][1])

rows = []
for market, strategy, symbol in sorted(grouped):
    metric_keys = grouped[(market, strategy, symbol)]
    buy_sum = sum_points(ts_range(metric_keys.get("Buy")))
    sell_sum = sum_points(ts_range(metric_keys.get("Sell")))
    netpos_last = last_value(ts_range(metric_keys.get("Netpos")))
    rpnl_last = last_value(ts_range(metric_keys.get("NetRpnl")))
    unpnl_last = last_value(ts_range(metric_keys.get("NetUpnl")))
    rpnlwfees_last = last_value(ts_range(metric_keys.get("RpnlWFees")))
    trade_count = int(last_value(ts_range(metric_keys.get("Trade"))))
    volume = buy_sum - sell_sum
    npnl = rpnl_last + unpnl_last
    npnl_ratio = 0.0 if volume == 0 else (npnl / volume) * 100
    rows.append({{
        "market": market,
        "strategy": strategy,
        "symbol": symbol,
        "volume_$": round(volume, 4),
        "net_position": round(netpos_last, 4),
        "net_position_$": round(netpos_last, 4),
        "rpnl": round(rpnl_last, 4),
        "unpnl": round(unpnl_last, 4),
        "rpnlwfees": round(rpnlwfees_last, 4),
        "npnl_r+un": round(npnl, 4),
        "npnl/volume_%": f"{{npnl_ratio:.4f}}%",
        "trade_count": trade_count,
    }})

print(json.dumps(rows))
"""


def export_rows_via_ssh(
    *,
    config: RedisConfig,
    start_ms: int,
    end_ms: int,
) -> list[dict[str, Any]]:
    remote_script = build_remote_export_script(
        {
            "host": config.host,
            "port": config.port,
            "username": config.username,
            "password": config.password,
            "db": config.db,
            "decode_responses": True,
        },
        start_ms,
        end_ms,
    )
    shell_script = f"""
cd {shlex.quote(config.ssh_workdir)}
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python - <<'PY'
{remote_script}
PY
fi
exec python3 - <<'PY'
{remote_script}
PY
"""
    completed = subprocess.run(
        ["ssh", "-q", "-T", config.ssh_host, shell_script],
        capture_output=True,
        check=False,
        encoding="utf-8",
        timeout=300,
    )
    if completed.returncode != 0:
        body = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"ssh redis net pnl export failed with exit {completed.returncode}: {body}"
        )
    return json.loads(completed.stdout)


def export_rows_locally(
    *,
    client: RedisClient,
    start_ms: int,
    end_ms: int,
) -> list[dict[str, Any]]:
    grouped_keys = group_metric_keys(list(client.scan_iter(count=1000)))

    def fetch_series(key: str | None) -> list[list[Any]]:
        if key is None:
            return []
        return client.ts_range(key, start_ms, end_ms)

    return build_rows_from_grouped_keys(grouped_keys, fetch_series)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export 24h Redis PnL data into the net_pnl raw CSV contract."
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--db", type=int, default=None)
    parser.add_argument(
        "--execution-mode",
        choices=["ssh", "local"],
        default=None,
        help="Run Redis export locally or through SSH.",
    )
    parser.add_argument("--ssh-host", default=None)
    parser.add_argument("--ssh-workdir", default=None)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--output", default="data/trades.csv")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> RedisConfig:
    defaults = RedisConfig.from_env()
    return RedisConfig(
        host=args.host or defaults.host,
        port=args.port if args.port is not None else defaults.port,
        username=args.username if args.username is not None else defaults.username,
        password=args.password if args.password is not None else defaults.password,
        db=args.db if args.db is not None else defaults.db,
        execution_mode=(
            args.execution_mode
            if args.execution_mode is not None
            else defaults.execution_mode
        ),
        ssh_host=args.ssh_host or defaults.ssh_host,
        ssh_workdir=args.ssh_workdir or defaults.ssh_workdir,
    )


def save_rows(rows: list[dict[str, Any]], output_path: str) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=ANALYSIS_DATA_COLUMNS)
    df.to_csv(out_path, index=False)
    return out_path


def main() -> Path:
    args = parse_args()
    config = build_config(args)
    start_ms, end_ms = time_window_bounds(args.window_hours)

    if config.execution_mode == "ssh":
        rows = export_rows_via_ssh(config=config, start_ms=start_ms, end_ms=end_ms)
    else:
        client = RedisClient(
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            db=config.db,
            execution_mode="local",
        )
        try:
            rows = export_rows_locally(client=client, start_ms=start_ms, end_ms=end_ms)
        finally:
            client.close()

    out_path = save_rows(rows, args.output)
    print(f"Saved {len(rows)} rows to {out_path}")
    return out_path


if __name__ == "__main__":
    main()
