from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.clients.exchanges.binance import BinanceClient
from src.clients.exchanges.bybit import BybitClient
from src.clients.exchanges.gateio import GateioClient
from src.clients.exchanges.kucoin import KucoinClient

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "alt_liquidity.json"


def load_liquidity_row_configs(symbol: str) -> list[dict[str, Any]]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rows = payload.get(symbol.upper())
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No liquidity configuration found for {symbol.upper()}.")
    return rows


def build_public_clients() -> dict[str, Any]:
    return {
        "binance": BinanceClient(),
        "bybit": BybitClient(),
        "gateio": GateioClient(),
        "kucoin": KucoinClient(),
    }


def load_public_liquidity_metrics(
    exchange_client: Any,
    public_symbol: str,
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> tuple[float | None, float | None, pd.DataFrame]:
    order_book = exchange_client.get_spot_order_book(public_symbol)
    market_plus_depth, market_minus_depth = calculate_depth_totals(order_book)
    public_volume_history = exchange_client.get_spot_quote_volume_history(
        public_symbol,
        days=days,
        report_date=report_date,
    )
    return market_plus_depth, market_minus_depth, public_volume_history


def calculate_depth_totals(
    order_book: dict[str, Any],
) -> tuple[float | None, float | None]:
    bids = order_book.get("bids")
    asks = order_book.get("asks")
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        return None, None

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid_price = (best_bid + best_ask) / 2
    lower_bound = mid_price * 0.98
    upper_bound = mid_price * 1.02

    market_minus_depth = sum(
        float(price) * float(size)
        for price, size in bids
        if lower_bound <= float(price) <= mid_price
    )
    market_plus_depth = sum(
        float(price) * float(size)
        for price, size in asks
        if mid_price <= float(price) <= upper_bound
    )
    return market_plus_depth, market_minus_depth


def calculate_period_market_share(
    trade_history: pd.DataFrame,
    public_volume_history: pd.DataFrame,
) -> float | None:
    if public_volume_history.empty:
        return None

    public_df = public_volume_history.copy()
    public_df["date"] = pd.to_datetime(public_df["date"]).dt.floor("D")
    public_df = public_df.groupby("date", as_index=False).agg(
        quote_volume=("quote_volume", "sum")
    )
    trade_df = (
        trade_history.groupby("date", as_index=False).agg(
            our_notional=("our_notional", "sum")
        )
        if not trade_history.empty
        else pd.DataFrame(columns=["date", "our_notional"])
    )
    merged = public_df.merge(trade_df, on="date", how="left")
    merged["our_notional"] = merged["our_notional"].fillna(0.0)
    merged = merged[merged["quote_volume"] > 0]
    if merged.empty:
        return None

    total_quote_volume = float(merged["quote_volume"].sum())
    if total_quote_volume <= 0:
        return None
    return float(merged["our_notional"].sum()) / total_quote_volume
