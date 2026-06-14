from __future__ import annotations

import argparse
from datetime import datetime
from itertools import islice
import logging
from pathlib import Path
import re
import time
from typing import Any, Iterable

import pandas as pd

from src.clients.databases.redis import RedisClient
from src.clients.rcj_trading import (
    RcjTradingAnalyzeType,
    RcjTradingClient,
)
from src.settings import get_settings
from src.utils.constants import ANALYSIS_DATA_COLUMNS

DEFAULT_PERIOD_MS = 24 * 60 * 60 * 1000
DEFAULT_BATCH_SIZE = 100
logger = logging.getLogger(__name__)
REDIS_EXCHANGE_PREFIXES = {"BIN", "BYB", "GAT", "KUC", "OKX"}


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


def load_symbols_by_market_from_input(
    input_path: str | Path,
) -> dict[str, list[str]]:
    """Load unique spot and perp symbols from the configured net P&L input CSV."""
    input_df = pd.read_csv(input_path)
    source_columns = {
        str(column).strip().lower(): column for column in input_df.columns
    }
    if {"market", "symbol"} <= source_columns.keys():
        input_df = input_df.loc[
            :, [source_columns["market"], source_columns["symbol"]]
        ].rename(
            columns={
                source_columns["market"]: "market",
                source_columns["symbol"]: "symbol",
            }
        )
    elif len(input_df.columns) == len(ANALYSIS_DATA_COLUMNS):
        input_df.columns = ANALYSIS_DATA_COLUMNS
        input_df = input_df.loc[:, ["market", "symbol"]]
    else:
        raise ValueError(
            f"{input_path} must contain market and symbol columns or match the "
            "configured net P&L column order."
        )
    input_df = input_df.dropna()
    input_df["market"] = input_df["market"].astype(str).str.strip().str.lower()
    input_df["symbol"] = input_df["symbol"].astype(str).str.strip()
    input_df = input_df[input_df["symbol"] != ""]
    return {
        market: sorted(
            input_df.loc[input_df["market"] == market, "symbol"].drop_duplicates()
        )
        for market in ("spot", "perp")
    }


def get_symbols_by_market_with_fallback(
    redis_client: RedisClient,
    market: str,
    input_path: str | Path,
) -> list[str]:
    """Load market symbols from Redis, falling back to the net P&L input CSV."""
    try:
        symbols = redis_client.get_symbols_by_market(market)  # pyrefly: ignore
        if symbols:
            return symbols
        logger.warning("Redis returned no %s symbols; using %s.", market, input_path)
    except Exception:
        logger.warning(
            "Failed to load %s symbols from Redis; using %s.",
            market,
            input_path,
            exc_info=True,
        )

    symbols = load_symbols_by_market_from_input(input_path)[market]
    logger.info("Loaded %s %s symbols from %s.", len(symbols), market, input_path)
    return symbols


def metric_delta(metric: dict[str, Any], *, absolute: bool = False) -> float:
    first = float(metric.get("first", 0) or 0)
    last = float(metric.get("last", 0) or 0)
    delta = last - first
    return abs(delta) if absolute else delta


def redis_metric_delta(metric: dict[str, Any], *, absolute: bool = False) -> float:
    delta = float(metric.get("delta", 0) or 0)
    return abs(delta) if absolute else delta


def normalize_redis_strategy(strategy: str) -> str:
    compact = str(strategy).strip().upper()
    if compact == "KUCHP":
        return "strategy5"
    if compact == "KUCPOSDIFF":
        return "strategy11"

    match = re.fullmatch(r"([A-Z]+?)(\d+)?", compact)
    if not match:
        return compact.lower()

    prefix, digits = match.groups()
    if digits is None:
        return "strategy1" if prefix in REDIS_EXCHANGE_PREFIXES else compact.lower()
    if digits == "42":
        return "kucc4-2" if prefix == "KUC" else "strategy4-2"
    if digits == "92":
        return "kucc9-2" if prefix == "KUC" else "strategy9-2"
    if digits == "4":
        return "kucc4" if prefix == "KUC" else "strategy4"

    if digits in {"2", "3", "5", "7", "8", "9", "10", "11", "12", "13"}:
        return f"strategy{digits}"
    return compact.lower()


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
            npnl = rpnlwfees + unpnl
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


def build_analysis_rows_from_redis(
    payload: dict[str, dict[str, Any]],
    *,
    market: str,
    symbol: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_strategy, metrics in sorted(payload.items()):
        strategy = normalize_redis_strategy(raw_strategy)
        net_position = redis_metric_delta(metrics.get("Netpos", {}))
        rpnl = redis_metric_delta(metrics.get("Rpnl", {}))
        unpnl = redis_metric_delta(metrics.get("Upnl", {}))
        rpnlwfees = redis_metric_delta(metrics.get("RpnlWFees", {}))
        npnl = rpnlwfees + unpnl

        # Redis exploration keys currently expose PnL and net position but not
        # the volume, trade count, or net position dollar series used by the API.
        rows.append(
            {
                "market": market,
                "strategy": strategy,
                "symbol": symbol,
                "volume_$": 0.0,
                "net_position": round(net_position, 4),
                "net_position_$": 0.0,
                "rpnl": round(rpnl, 4),
                "unpnl": round(unpnl, 4),
                "rpnlwfees": round(rpnlwfees, 4),
                "npnl_r+un": round(npnl, 4),
                "npnl/volume_%": "0.0000%",
                "trade_count": 0,
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


def build_market_analysis_dataframe_from_redis(
    *,
    market: str,
    symbols: list[str],
    period_ms: int = DEFAULT_PERIOD_MS,
    redis_client: RedisClient | None = None,
) -> pd.DataFrame:
    client = redis_client or RedisClient(execution_mode="ssh", ssh_host="T1_newuser1")
    should_close = redis_client is None
    try:
        rows: list[dict[str, Any]] = []
        for symbol in symbols:
            payload = client.get_strategy_metrics_for_market_symbol(
                market,
                symbol,
                period_ms=period_ms,
            )
            rows.extend(
                build_analysis_rows_from_redis(payload, market=market, symbol=symbol)
            )
    finally:
        if should_close:
            client.close()

    if not rows:
        return pd.DataFrame(columns=ANALYSIS_DATA_COLUMNS)

    df = pd.DataFrame(rows, columns=ANALYSIS_DATA_COLUMNS)
    numeric_cols = [
        "volume_$",
        "net_position",
        "net_position_$",
        "rpnl",
        "unpnl",
        "rpnlwfees",
        "npnl_r+un",
        "trade_count",
    ]
    grouped = (
        df.groupby(["market", "strategy", "symbol"], as_index=False)[numeric_cols]
        .sum()
        .loc[:, ["market", "strategy", "symbol", *numeric_cols]]
    )
    grouped["npnl/volume_%"] = "0.0000%"
    grouped["trade_count"] = grouped["trade_count"].astype(int)
    return grouped.loc[:, ANALYSIS_DATA_COLUMNS]


def build_analysis_dataframe(
    *,
    period_ms: int = DEFAULT_PERIOD_MS,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> pd.DataFrame:
    redis_client = RedisClient(execution_mode="ssh", ssh_host="T1_newuser1")
    trading_client = RcjTradingClient()
    input_path = get_settings().net_pnl_input_path
    try:
        spot_start = time.time()
        spot_symbols = get_symbols_by_market_with_fallback(
            redis_client,
            "spot",
            input_path,
        )
        logger.info(
            "Loaded %s spot symbols in %.2f seconds.",
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
        perp_symbols = get_symbols_by_market_with_fallback(
            redis_client,
            "perp",
            input_path,
        )
        logger.info(
            "Loaded %s perp symbols in %.2f seconds.",
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
        period_ms=24 * 60 * 60 * 1000, market="spot", symbols=["BTC"]
    )
    print("api")
    print(df)
    redis_df = build_market_analysis_dataframe_from_redis(
        period_ms=24 * 60 * 60 * 1000, market="spot", symbols=["BTC"]
    )
    print("redis")
    print(redis_df)
