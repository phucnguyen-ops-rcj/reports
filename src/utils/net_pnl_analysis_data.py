from __future__ import annotations

import argparse
from datetime import datetime
from itertools import islice
import logging
from pathlib import Path
import time
from typing import Any, Iterable

import pandas as pd

from src.clients.databases.redis import RedisClient
from src.clients.rcj_trading import (
    RcjTradingAnalyzeType,
    RcjTradingClient,
)
from src.utils.constants import ANALYSIS_DATA_COLUMNS

DEFAULT_PERIOD_MS = 24 * 60 * 60 * 1000
DEFAULT_BATCH_SIZE = 100
logger = logging.getLogger(__name__)


def _ordinal_suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def default_output_path(now: datetime | None = None) -> str:
    current = now or datetime.now()
    month = current.strftime("%b")
    day = current.day
    return f"data/net_pnl/analysis_data_{month}_{day}{_ordinal_suffix(day)}.csv"


def batched(items: Iterable[str], size: int) -> Iterable[list[str]]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def metric_delta(metric: dict[str, Any], *, absolute: bool = False) -> float:
    first = float(metric.get("first", 0) or 0)
    last = float(metric.get("last", 0) or 0)
    delta = last - first
    return abs(delta) if absolute else delta


def build_analysis_rows(
    payload: dict[str, Any],
    *,
    market: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy, symbol_map in sorted(payload.items()):
        for symbol, metrics in sorted(symbol_map.items()):
            if not symbol:
                continue

            volume = metric_delta(metrics.get("tradeVolume", {}), absolute=True)
            trade_count = int(metric_delta(metrics.get("count", {}), absolute=True))
            net_position = metric_delta(metrics.get("netPos", {}))
            net_position_dol = metric_delta(metrics.get("netPosDol", {}))
            rpnl = metric_delta(metrics.get("rpnl", {}))
            unpnl = metric_delta(metrics.get("upnl", {}))
            rpnlwfees = metric_delta(metrics.get("rpnlWFees", {}))
            npnl = rpnl + unpnl
            npnl_ratio = 0.0 if volume == 0 else (npnl / volume) * 100

            rows.append(
                {
                    "market": market,
                    "strategy": strategy,
                    "symbol": symbol,
                    "volume_$": round(volume, 4),
                    "net_position": round(net_position, 4),
                    "net_position_$": round(net_position_dol, 4),
                    "rpnl": round(rpnl, 4),
                    "unpnl": round(unpnl, 4),
                    "rpnlwfees": round(rpnlwfees, 4),
                    "npnl_r+un": round(npnl, 4),
                    "npnl/volume_%": f"{npnl_ratio:.4f}%",
                    "trade_count": trade_count,
                }
            )
    return rows


def fetch_market_rows(
    *,
    trading_client: RcjTradingClient,
    market: str,
    symbols: list[str],
    period_ms: int,
    batch_size: int,
) -> list[dict[str, Any]]:
    analyze_type = (
        RcjTradingAnalyzeType.SPOT if market == "spot" else RcjTradingAnalyzeType.PERP
    )
    rows: list[dict[str, Any]] = []
    for symbol_batch in batched(symbols, batch_size):
        payload = trading_client.get_analyze(
            symbols=symbol_batch,
            period_ms=period_ms,
            analyze_type=analyze_type,
        )
        rows.extend(build_analysis_rows(payload, market=market))
    return rows


def build_market_analysis_dataframe(
    *,
    market: str,
    symbols: list[str],
    period_ms: int = DEFAULT_PERIOD_MS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    trading_client: RcjTradingClient | None = None,
) -> pd.DataFrame:
    client = trading_client or RcjTradingClient()
    rows = fetch_market_rows(
        trading_client=client,
        market=market,
        symbols=symbols,
        period_ms=period_ms,
        batch_size=batch_size,
    )
    return pd.DataFrame(rows, columns=ANALYSIS_DATA_COLUMNS)


def build_analysis_dataframe(
    *,
    period_ms: int = DEFAULT_PERIOD_MS,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> pd.DataFrame:
    redis_client = RedisClient(execution_mode="ssh", ssh_host="T1_newuser1")
    trading_client = RcjTradingClient()
    try:
        spot_start = time.time()
        spot_symbols = redis_client.get_symbols_by_market("spot")
        logger.info(
            "Loaded %s spot symbols from Redis in %.2f seconds.",
            len(spot_symbols),
            time.time() - spot_start,
        )
        rows = fetch_market_rows(
            trading_client=trading_client,
            market="spot",
            symbols=spot_symbols,
            period_ms=period_ms,
            batch_size=batch_size,
        )
        perp_start = time.time()
        perp_symbols = redis_client.get_symbols_by_market("perp")
        logger.info(
            "Loaded %s perp symbols from Redis in %.2f seconds.",
            len(perp_symbols),
            time.time() - perp_start,
        )
        rows.extend(
            fetch_market_rows(
                trading_client=trading_client,
                market="perp",
                symbols=perp_symbols,
                period_ms=period_ms,
                batch_size=batch_size,
            )
        )
    finally:
        redis_client.close()

    return pd.DataFrame(rows, columns=ANALYSIS_DATA_COLUMNS)


def export_analysis_data(
    *,
    output_path: str | None = None,
    period_ms: int = DEFAULT_PERIOD_MS,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Path:
    df = build_analysis_dataframe(period_ms=period_ms, batch_size=batch_size)
    out_path = Path(output_path or default_output_path())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export RCJ trading analysis data for net_pnl from Redis symbols."
    )
    parser.add_argument("--output", default=None)
    parser.add_argument("--period-ms", type=int, default=DEFAULT_PERIOD_MS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser.parse_args()


def main() -> Path:
    args = parse_args()
    output_path = export_analysis_data(
        output_path=args.output,
        period_ms=args.period_ms,
        batch_size=args.batch_size,
    )
    print(output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    df = build_market_analysis_dataframe(
        period_ms=24 * 60 * 60 * 1000, market="perp", symbols=["BLUAI"]
    )
    print(df)
