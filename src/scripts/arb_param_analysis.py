from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.clients.binance import BinanceClient
from src.clients.kucoin import KucoinClient


DEFAULT_MODEL_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "arb_param_analysis.json"
)


@dataclass(frozen=True)
class MarketLeg:
    exchange: str
    market: str
    side: str
    symbol: str
    base_currency: str
    quote_currency: str


@dataclass(frozen=True)
class RiskConfig:
    max_allowed_taker_slippage_bps: float
    max_order_fraction_of_10bps_depth: float
    max_order_fraction_of_1m_p10_volume: float
    max_position_size_usdt: float
    max_settle_size_usdt: float
    update_order_frequency_s: float
    min_useful_maker_usdt: float
    min_useful_taker_usdt: float
    candidate_sizes_usdt: list[float]
    maker_max_settle_fraction: float
    maker_max_position_fraction: float
    taker_maker_min_multiplier: float
    taker_max_settle_fraction: float
    taker_max_position_fraction: float
    tier_thresholds: dict[str, dict[str, float]]
    sleep_multipliers_by_tier: dict[str, float]
    min_sleep_s: int
    max_sleep_s: int


def main() -> None:
    args = _parse_args()
    risk = RiskConfig(
        max_allowed_taker_slippage_bps=args.max_allowed_taker_slippage_bps,
        max_order_fraction_of_10bps_depth=args.max_order_fraction_of_10bps_depth,
        max_order_fraction_of_1m_p10_volume=args.max_order_fraction_of_1m_p10_volume,
        max_position_size_usdt=args.max_position_size_usdt,
        max_settle_size_usdt=args.max_settle_size_usdt,
        update_order_frequency_s=args.update_order_frequency_s,
        min_useful_maker_usdt=args.min_useful_maker_usdt,
        min_useful_taker_usdt=args.min_useful_taker_usdt,
        candidate_sizes_usdt=args.candidate_sizes_usdt,
        maker_max_settle_fraction=args.maker_max_settle_fraction,
        maker_max_position_fraction=args.maker_max_position_fraction,
        taker_maker_min_multiplier=args.taker_maker_min_multiplier,
        taker_max_settle_fraction=args.taker_max_settle_fraction,
        taker_max_position_fraction=args.taker_max_position_fraction,
        tier_thresholds=args.tier_thresholds,
        sleep_multipliers_by_tier=args.sleep_multipliers_by_tier,
        min_sleep_s=args.min_sleep_s,
        max_sleep_s=args.max_sleep_s,
    )
    maker = MarketLeg(
        exchange=args.maker_exchange.lower(),
        market=args.maker_market.lower(),
        side=args.maker_side.lower(),
        symbol=args.maker_symbol
        or _derive_symbol(
            args.maker_exchange,
            args.maker_market,
            args.base_currency,
            args.quote_currency,
        ),
        base_currency=args.base_currency.upper(),
        quote_currency=args.quote_currency.upper(),
    )
    taker = MarketLeg(
        exchange=args.taker_exchange.lower(),
        market=args.taker_market.lower(),
        side=args.taker_side.lower(),
        symbol=args.taker_symbol
        or _derive_symbol(
            args.taker_exchange,
            args.taker_market,
            args.base_currency,
            args.quote_currency,
        ),
        base_currency=args.base_currency.upper(),
        quote_currency=args.quote_currency.upper(),
    )

    result = analyze_arbitrage_params(
        maker=maker,
        taker=taker,
        risk=risk,
        phase=args.phase,
        duration_s=args.duration_s,
        interval_s=args.interval_s,
        book_limit=args.book_limit,
        candle_minutes=args.candle_minutes,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_json_dumps(result) + "\n", encoding="utf-8")

    print(_json_dumps(result))


def analyze_arbitrage_params(
    *,
    maker: MarketLeg,
    taker: MarketLeg,
    risk: RiskConfig,
    phase: int,
    duration_s: int,
    interval_s: int,
    book_limit: int,
    candle_minutes: int,
) -> dict[str, Any]:
    if phase not in {1, 2}:
        raise ValueError("phase must be 1 or 2.")

    clients: dict[str, Any] = {}
    iterations = 1 if phase == 1 else max(1, math.ceil(duration_s / interval_s))
    maker_snapshots: list[dict[str, Any]] = []
    taker_snapshots: list[dict[str, Any]] = []

    for idx in range(iterations):
        maker_snapshots.append(
            _fetch_leg_snapshot(
                maker,
                clients=clients,
                candidate_sizes=risk.candidate_sizes_usdt,
                book_limit=book_limit,
                candle_minutes=candle_minutes,
            )
        )
        taker_snapshots.append(
            _fetch_leg_snapshot(
                taker,
                clients=clients,
                candidate_sizes=risk.candidate_sizes_usdt,
                book_limit=book_limit,
                candle_minutes=candle_minutes,
            )
        )
        if phase == 2 and idx < iterations - 1:
            time.sleep(interval_s)

    maker_metrics = _aggregate_leg_snapshots(maker, maker_snapshots)
    taker_metrics = _aggregate_leg_snapshots(taker, taker_snapshots)
    recommendation = _recommend_params(
        maker=maker,
        taker=taker,
        maker_metrics=maker_metrics,
        taker_metrics=taker_metrics,
        risk=risk,
    )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "sampling": {
            "snapshots": iterations,
            "duration_s": 0 if phase == 1 else duration_s,
            "interval_s": 0 if phase == 1 else interval_s,
            "book_limit": book_limit,
            "candle_minutes": candle_minutes,
        },
        "maker": asdict(maker),
        "taker": asdict(taker),
        "risk": asdict(risk),
        "metrics": {
            "maker": maker_metrics,
            "taker": taker_metrics,
        },
        "recommendation": recommendation,
    }


def _fetch_leg_snapshot(
    leg: MarketLeg,
    *,
    clients: dict[str, Any],
    candidate_sizes: list[float],
    book_limit: int,
    candle_minutes: int,
) -> dict[str, Any]:
    client = _client_for(leg.exchange, clients)
    rules = _fetch_symbol_rules(client, leg)
    book = _fetch_order_book(client, leg, book_limit)
    quantity_multiplier = (
        _to_float(rules.get("multiplier")) or 1.0
        if leg.exchange == "kucoin" and leg.market == "perp"
        else 1.0
    )
    levels = {
        "bids": _normalize_levels(
            book.get("bids", []),
            reverse=True,
            quantity_multiplier=quantity_multiplier,
        ),
        "asks": _normalize_levels(
            book.get("asks", []),
            reverse=False,
            quantity_multiplier=quantity_multiplier,
        ),
    }
    book_metrics = _compute_book_metrics(
        levels,
        taker_side=leg.side,
        candidate_sizes=candidate_sizes,
    )
    candle_turnovers = _fetch_recent_1m_turnovers(
        client,
        leg,
        candle_minutes=candle_minutes,
    )
    volume_24h = _fetch_24h_quote_volume(client, leg)
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "rules": rules,
        "book": book_metrics,
        "recent_1m_turnover_usdt": candle_turnovers,
        "quote_volume_24h_usdt": volume_24h,
    }


def _fetch_symbol_rules(client: Any, leg: MarketLeg) -> dict[str, Any]:
    if leg.exchange == "binance":
        return client.get_symbol_rules(leg.symbol, market=leg.market)
    if leg.exchange == "kucoin" and leg.market == "spot":
        return client.get_spot_symbol_rules(leg.symbol)
    if leg.exchange == "kucoin" and leg.market == "perp":
        return client.get_futures_symbol_rules(leg.symbol)
    raise ValueError(f"Unsupported leg for rules: {leg.exchange} {leg.market}")


def _fetch_order_book(client: Any, leg: MarketLeg, limit: int) -> dict[str, Any]:
    if leg.exchange == "binance" and leg.market == "spot":
        return client.get_order_book(leg.symbol, limit=limit)
    if leg.exchange == "binance" and leg.market == "perp":
        return client.get_futures_order_book(leg.symbol, limit=limit)
    if leg.exchange == "kucoin" and leg.market == "spot":
        return client.get_spot_order_book(leg.symbol, limit=limit)
    if leg.exchange == "kucoin" and leg.market == "perp":
        return client.get_futures_order_book(leg.symbol, limit=limit)
    raise ValueError(f"Unsupported leg for order book: {leg.exchange} {leg.market}")


def _fetch_24h_quote_volume(client: Any, leg: MarketLeg) -> float | None:
    try:
        if leg.exchange == "binance" and leg.market == "spot":
            return client.get_24h_ticker(leg.symbol).quote_volume
        if leg.exchange == "binance" and leg.market == "perp":
            return client.get_futures_24h_ticker(leg.symbol).quote_volume
        if leg.exchange == "kucoin":
            token = leg.base_currency if leg.market == "spot" else leg.symbol
            df = client.get_trading_volume([token])
            if df.empty:
                return None
            value = df.iloc[0]["usd_volume_24h"]
            return _to_float(value)
    except Exception:
        return None
    return None


def _fetch_recent_1m_turnovers(
    client: Any,
    leg: MarketLeg,
    *,
    candle_minutes: int,
) -> list[float]:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(minutes=candle_minutes + 2)
    try:
        if leg.exchange == "binance":
            if leg.market == "spot":
                candles = client.get_klines(
                    leg.symbol, interval="1m", limit=candle_minutes
                )
            else:
                candles = client.get_futures_klines(
                    leg.symbol,
                    interval="1m",
                    limit=candle_minutes,
                )
            return [
                value
                for value in (candle.quote_volume for candle in candles)
                if value is not None
            ]
        if leg.exchange == "kucoin" and leg.market == "spot":
            rows = client.get_spot_klines(
                leg.symbol,
                interval="1min",
                start_at_s=int(start_dt.timestamp()),
                end_at_s=int(end_dt.timestamp()),
            )
            return _turnovers_from_kucoin_rows(rows)
        if leg.exchange == "kucoin" and leg.market == "perp":
            rows = client.get_futures_klines(
                leg.symbol,
                granularity=1,
                start_at_ms=int(start_dt.timestamp() * 1000),
                end_at_ms=int(end_dt.timestamp() * 1000),
            )
            return _turnovers_from_kucoin_rows(rows)
    except Exception:
        return []
    return []


def _compute_book_metrics(
    levels: dict[str, list[tuple[float, float]]],
    *,
    taker_side: str,
    candidate_sizes: list[float],
) -> dict[str, Any]:
    bids = levels["bids"]
    asks = levels["asks"]
    if not bids or not asks:
        raise ValueError("Order book must contain bids and asks.")

    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 10000

    bid_depth = {
        str(bps): _depth_within_bps(bids, mid=mid, bps=bps, side="bid")
        for bps in (10, 25, 50)
    }
    ask_depth = {
        str(bps): _depth_within_bps(asks, mid=mid, bps=bps, side="ask")
        for bps in (10, 25, 50)
    }
    slippage = {
        _size_key(size): _simulate_taker_slippage_bps(
            bids=bids,
            asks=asks,
            mid=mid,
            quote_size_usdt=size,
            side=taker_side,
        )
        for size in candidate_sizes
    }
    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid,
        "spread_bps": spread_bps,
        "top_bid_usdt": bids[0][0] * bids[0][1],
        "top_ask_usdt": asks[0][0] * asks[0][1],
        "bid_depth_usdt_within_bps": bid_depth,
        "ask_depth_usdt_within_bps": ask_depth,
        "taker_slippage_bps_by_size_usdt": slippage,
    }


def _aggregate_leg_snapshots(
    leg: MarketLeg,
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    rules = snapshots[-1]["rules"]
    books = [item["book"] for item in snapshots]
    turnovers = [
        value
        for item in snapshots
        for value in item.get("recent_1m_turnover_usdt", [])
        if value is not None
    ]
    candidate_keys = sorted(
        books[-1]["taker_slippage_bps_by_size_usdt"].keys(),
        key=lambda value: float(value),
    )
    return {
        "symbol": leg.symbol,
        "exchange": leg.exchange,
        "market": leg.market,
        "side": leg.side,
        "snapshot_count": len(snapshots),
        "rules": rules,
        "spread_bps_p50": _percentile(
            [book["spread_bps"] for book in books],
            50,
        ),
        "spread_bps_p90": _percentile(
            [book["spread_bps"] for book in books],
            90,
        ),
        "mid_price_p50": _percentile(
            [book["mid_price"] for book in books],
            50,
        ),
        "bid_depth_10bps_usdt_p10": _percentile(
            [book["bid_depth_usdt_within_bps"]["10"] for book in books],
            10,
        ),
        "ask_depth_10bps_usdt_p10": _percentile(
            [book["ask_depth_usdt_within_bps"]["10"] for book in books],
            10,
        ),
        "bid_depth_25bps_usdt_p10": _percentile(
            [book["bid_depth_usdt_within_bps"]["25"] for book in books],
            10,
        ),
        "ask_depth_25bps_usdt_p10": _percentile(
            [book["ask_depth_usdt_within_bps"]["25"] for book in books],
            10,
        ),
        "recent_1m_turnover_usdt_p10": _percentile(turnovers, 10),
        "recent_1m_turnover_usdt_p50": _percentile(turnovers, 50),
        "quote_volume_24h_usdt_p50": _percentile(
            [
                item["quote_volume_24h_usdt"]
                for item in snapshots
                if item["quote_volume_24h_usdt"] is not None
            ],
            50,
        ),
        "taker_slippage_bps_p90_by_size_usdt": {
            key: _percentile(
                [
                    book["taker_slippage_bps_by_size_usdt"].get(key)
                    for book in books
                    if book["taker_slippage_bps_by_size_usdt"].get(key) is not None
                ],
                90,
            )
            for key in candidate_keys
        },
    }


def _recommend_params(
    *,
    maker: MarketLeg,
    taker: MarketLeg,
    maker_metrics: dict[str, Any],
    taker_metrics: dict[str, Any],
    risk: RiskConfig,
) -> dict[str, Any]:
    maker_tier = _classify_leg_tier(maker, maker_metrics, risk)
    taker_tier = _classify_leg_tier(taker, taker_metrics, risk)
    maker_min, maker_reasons = _choose_maker_min_order_size(
        maker,
        maker_metrics,
        risk,
    )
    taker_min, taker_reasons = _choose_taker_min_order_size(
        taker,
        taker_metrics,
        risk,
        maker_min_order_size=maker_min,
    )
    maker_sleep = _sleep_for_tier(maker_tier, risk)
    taker_sleep = _sleep_for_tier(taker_tier, risk)
    return {
        "maker_tier": maker_tier,
        "taker_tier": taker_tier,
        "params": {
            "maker_fill_sleep": maker_sleep,
            "taker_fill_sleep": taker_sleep,
            "maker_min_order_size": maker_min,
            "taker_min_order_size": taker_min,
        },
        "reasons": maker_reasons + taker_reasons,
    }


def _choose_maker_min_order_size(
    leg: MarketLeg,
    metrics: dict[str, Any],
    risk: RiskConfig,
) -> tuple[float, list[str]]:
    exchange_floor = _exchange_floor_usdt(metrics)
    floor = max(exchange_floor, risk.min_useful_maker_usdt)
    relevant_depth = _relevant_depth_10bps(leg, metrics)
    depth_cap = relevant_depth * risk.max_order_fraction_of_10bps_depth
    volume_p10 = metrics.get("recent_1m_turnover_usdt_p10")
    volume_cap = (
        volume_p10 * risk.max_order_fraction_of_1m_p10_volume
        if volume_p10 is not None
        else math.inf
    )
    hard_cap = min(
        risk.max_settle_size_usdt * risk.maker_max_settle_fraction,
        risk.max_position_size_usdt * risk.maker_max_position_fraction,
        depth_cap,
        volume_cap,
    )
    value = _first_candidate_between(risk.candidate_sizes_usdt, floor, hard_cap)
    reasons: list[str] = []
    if value is None:
        value = _round_usdt(floor)
        if floor > hard_cap:
            reasons.append(
                "Maker floor is above the conservative cap from depth, volume, or position limits."
            )
        reasons.append(
            "Maker minimum uses the floor because no candidate fit all depth/volume caps."
        )
    return value, reasons


def _choose_taker_min_order_size(
    leg: MarketLeg,
    metrics: dict[str, Any],
    risk: RiskConfig,
    *,
    maker_min_order_size: float,
) -> tuple[float, list[str]]:
    exchange_floor = _exchange_floor_usdt(metrics)
    floor = max(
        exchange_floor,
        risk.min_useful_taker_usdt,
        maker_min_order_size * risk.taker_maker_min_multiplier,
    )
    relevant_depth = _relevant_depth_10bps(leg, metrics)
    depth_cap = relevant_depth * risk.max_order_fraction_of_10bps_depth
    hard_cap = min(
        risk.max_settle_size_usdt * risk.taker_max_settle_fraction,
        risk.max_position_size_usdt * risk.taker_max_position_fraction,
        depth_cap,
    )
    slippage_by_size = metrics.get("taker_slippage_bps_p90_by_size_usdt", {})
    reasons: list[str] = []
    for candidate in risk.candidate_sizes_usdt:
        if candidate < floor or candidate > hard_cap:
            continue
        slippage = slippage_by_size.get(_size_key(candidate))
        if slippage is not None and slippage <= risk.max_allowed_taker_slippage_bps:
            return _round_usdt(candidate), reasons

    value = _round_usdt(floor)
    if floor > hard_cap:
        reasons.append(
            "Taker floor is above the conservative cap from depth or position limits."
        )
    reasons.append(
        "Taker minimum uses the floor because no candidate passed the slippage/depth caps."
    )
    return value, reasons


def _classify_leg_tier(
    leg: MarketLeg,
    metrics: dict[str, Any],
    risk: RiskConfig,
) -> str:
    spread = metrics.get("spread_bps_p50") or math.inf
    depth_10 = _relevant_depth_10bps(leg, metrics)
    volume_p10 = metrics.get("recent_1m_turnover_usdt_p10") or 0.0
    slippage_by_size = metrics.get("taker_slippage_bps_p90_by_size_usdt", {})

    for tier in ("A", "B"):
        thresholds = risk.tier_thresholds.get(tier, {})
        slippage_size = thresholds.get("slippage_check_size_usdt")
        slippage = (
            slippage_by_size.get(_size_key(slippage_size))
            if slippage_size is not None
            else None
        )
        if (
            spread <= thresholds.get("max_spread_bps", math.inf)
            and depth_10 >= thresholds.get("min_depth_10bps_usdt", 0.0)
            and volume_p10 >= thresholds.get("min_recent_1m_turnover_p10_usdt", 0.0)
            and slippage is not None
            and slippage <= risk.max_allowed_taker_slippage_bps
        ):
            return tier

    thresholds = risk.tier_thresholds.get("C", {})
    if (
        spread <= thresholds.get("max_spread_bps", math.inf)
        and depth_10 >= thresholds.get("min_depth_10bps_usdt", 0.0)
        and volume_p10 >= thresholds.get("min_recent_1m_turnover_p10_usdt", 0.0)
    ):
        return "C"
    return "D"


def _sleep_for_tier(tier: str, risk: RiskConfig) -> int:
    multiplier = risk.sleep_multipliers_by_tier.get(tier, 6.0)
    value = risk.update_order_frequency_s * multiplier
    return int(round(min(risk.max_sleep_s, max(risk.min_sleep_s, value))))


def _exchange_floor_usdt(metrics: dict[str, Any]) -> float:
    rules = metrics.get("rules", {})
    min_notional = _to_float(rules.get("min_notional"))
    if min_notional is not None:
        return min_notional
    min_qty = _to_float(rules.get("min_qty"))
    mid_price = _to_float(metrics.get("mid_price_p50"))
    if min_qty is not None and mid_price is not None:
        multiplier = _to_float(rules.get("multiplier")) or 1.0
        return min_qty * mid_price * multiplier
    return 0.0


def _relevant_depth_10bps(leg: MarketLeg, metrics: dict[str, Any]) -> float:
    if leg.side == "sell":
        return metrics.get("bid_depth_10bps_usdt_p10") or 0.0
    return metrics.get("ask_depth_10bps_usdt_p10") or 0.0


def _first_candidate_between(
    candidates: list[float],
    floor: float,
    cap: float,
) -> float | None:
    for candidate in candidates:
        if candidate >= floor and candidate <= cap:
            return _round_usdt(candidate)
    return None


def _depth_within_bps(
    levels: list[tuple[float, float]],
    *,
    mid: float,
    bps: int,
    side: str,
) -> float:
    if side == "bid":
        limit_price = mid * (1 - bps / 10000)
        return sum(price * qty for price, qty in levels if price >= limit_price)
    limit_price = mid * (1 + bps / 10000)
    return sum(price * qty for price, qty in levels if price <= limit_price)


def _simulate_taker_slippage_bps(
    *,
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    mid: float,
    quote_size_usdt: float,
    side: str,
) -> float | None:
    levels = asks if side == "buy" else bids
    remaining_quote = quote_size_usdt
    total_quote = 0.0
    total_base = 0.0
    for price, qty in levels:
        level_quote = price * qty
        quote_take = min(remaining_quote, level_quote)
        base_take = quote_take / price
        total_quote += quote_take
        total_base += base_take
        remaining_quote -= quote_take
        if remaining_quote <= 1e-9:
            break
    if remaining_quote > 1e-9 or total_base <= 0:
        return None
    avg_price = total_quote / total_base
    if side == "buy":
        return (avg_price - mid) / mid * 10000
    return (mid - avg_price) / mid * 10000


def _normalize_levels(
    raw_levels: Any,
    *,
    reverse: bool,
    quantity_multiplier: float = 1.0,
) -> list[tuple[float, float]]:
    levels: list[tuple[float, float]] = []
    for raw in raw_levels or []:
        if not isinstance(raw, list | tuple) or len(raw) < 2:
            continue
        price = _to_float(raw[0])
        qty = _to_float(raw[1])
        if price is None or qty is None or price <= 0 or qty <= 0:
            continue
        levels.append((price, qty * quantity_multiplier))
    return sorted(levels, key=lambda item: item[0], reverse=reverse)


def _turnovers_from_kucoin_rows(rows: list[list[Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        if len(row) < 7:
            continue
        turnover = _to_float(row[6])
        if turnover is not None:
            values.append(turnover)
    return values


def _percentile(values: list[float | None], percentile: float) -> float | None:
    filtered = sorted(value for value in values if value is not None)
    if not filtered:
        return None
    if len(filtered) == 1:
        return filtered[0]
    rank = (len(filtered) - 1) * percentile / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return filtered[int(rank)]
    lower_value = filtered[lower]
    upper_value = filtered[upper]
    return lower_value + (upper_value - lower_value) * (rank - lower)


def _client_for(exchange: str, clients: dict[str, Any]) -> Any:
    if exchange not in clients:
        if exchange == "binance":
            clients[exchange] = BinanceClient()
        elif exchange == "kucoin":
            clients[exchange] = KucoinClient()
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")
    return clients[exchange]


def _derive_symbol(exchange: str, market: str, base: str, quote: str) -> str:
    resolved_exchange = exchange.lower()
    resolved_market = market.lower()
    base = base.upper()
    quote = quote.upper()
    if resolved_exchange == "kucoin" and resolved_market == "spot":
        return f"{base}-{quote}"
    if resolved_exchange == "kucoin" and resolved_market == "perp":
        if base == "BTC":
            base = "XBT"
        return f"{base}{quote}M"
    return f"{base}{quote}"


def _parse_candidate_sizes(raw: str | list[Any]) -> list[float]:
    if isinstance(raw, list):
        raw_values = raw
    else:
        raw_values = raw.split(",")
    parsed = sorted(
        {
            value
            for value in (
                _to_float(item.strip() if isinstance(item, str) else item)
                for item in raw_values
            )
            if value is not None and value > 0
        }
    )
    if not parsed:
        raise ValueError("At least one positive candidate size is required.")
    return parsed


def _size_key(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _round_usdt(value: float) -> float:
    return round(float(value), 2)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _load_model_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"Model config must be a JSON object: {config_path}")
    return payload


def _parse_args() -> argparse.Namespace:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument(
        "--model-config",
        default=str(DEFAULT_MODEL_CONFIG_PATH),
        help="Path to JSON model policy config.",
    )
    pre_args, remaining_args = pre_parser.parse_known_args()
    model_config = _load_model_config(pre_args.model_config)
    defaults = model_config.get("defaults", {})
    order_size = model_config.get("order_size", {})
    maker_order_size = order_size.get("maker", {})
    taker_order_size = order_size.get("taker", {})
    sleep = model_config.get("sleep", {})

    parser = argparse.ArgumentParser(
        parents=[pre_parser],
        description=(
            "Analyze public order book and volume data to recommend simple "
            "arbitrage maker/taker size and fill-sleep parameters."
        ),
    )
    parser.add_argument("--phase", type=int, choices=[1, 2], default=1)
    parser.add_argument("--duration-s", type=int, default=300)
    parser.add_argument("--interval-s", type=int, default=5)
    parser.add_argument("--book-limit", type=int, default=100)
    parser.add_argument("--candle-minutes", type=int, default=60)
    parser.add_argument(
        "--maker-exchange", required=True, choices=["binance", "kucoin"]
    )
    parser.add_argument(
        "--taker-exchange", required=True, choices=["binance", "kucoin"]
    )
    parser.add_argument("--maker-market", required=True, choices=["spot", "perp"])
    parser.add_argument("--taker-market", required=True, choices=["spot", "perp"])
    parser.add_argument("--maker-side", required=True, choices=["buy", "sell"])
    parser.add_argument("--taker-side", required=True, choices=["buy", "sell"])
    parser.add_argument("--base-currency", required=True)
    parser.add_argument("--quote-currency", default="USDT")
    parser.add_argument("--maker-symbol")
    parser.add_argument("--taker-symbol")
    parser.add_argument(
        "--max-allowed-taker-slippage-bps",
        type=float,
        default=defaults.get("max_allowed_taker_slippage_bps", 5.0),
    )
    parser.add_argument(
        "--max-order-fraction-of-10bps-depth",
        type=float,
        default=defaults.get("max_order_fraction_of_10bps_depth", 0.05),
    )
    parser.add_argument(
        "--max-order-fraction-of-1m-p10-volume",
        type=float,
        default=defaults.get("max_order_fraction_of_1m_p10_volume", 0.2),
    )
    parser.add_argument(
        "--max-position-size-usdt",
        type=float,
        default=defaults.get("max_position_size_usdt", 200.0),
    )
    parser.add_argument(
        "--max-settle-size-usdt",
        type=float,
        default=defaults.get("max_settle_size_usdt", 100.0),
    )
    parser.add_argument(
        "--update-order-frequency-s",
        type=float,
        default=defaults.get("update_order_frequency_s", 10.0),
    )
    parser.add_argument(
        "--min-useful-maker-usdt",
        type=float,
        default=defaults.get("min_useful_maker_usdt", 10.0),
    )
    parser.add_argument(
        "--min-useful-taker-usdt",
        type=float,
        default=defaults.get("min_useful_taker_usdt", 15.0),
    )
    parser.add_argument(
        "--candidate-sizes",
        default=",".join(
            str(value)
            for value in defaults.get(
                "candidate_sizes_usdt",
                [5, 10, 15, 20, 25, 50, 75, 100],
            )
        ),
        help="Comma-separated USDT order sizes to test, for example 5,10,15,25,50.",
    )
    parser.add_argument("--output")
    args = parser.parse_args(remaining_args)
    args.model_config = pre_args.model_config
    args.candidate_sizes_usdt = _parse_candidate_sizes(args.candidate_sizes)
    args.maker_max_settle_fraction = float(
        maker_order_size.get("max_settle_fraction", 0.5)
    )
    args.maker_max_position_fraction = float(
        maker_order_size.get("max_position_fraction", 0.25)
    )
    args.taker_maker_min_multiplier = float(
        taker_order_size.get("maker_min_multiplier", 1.2)
    )
    args.taker_max_settle_fraction = float(
        taker_order_size.get("max_settle_fraction", 0.75)
    )
    args.taker_max_position_fraction = float(
        taker_order_size.get("max_position_fraction", 0.5)
    )
    args.tier_thresholds = {
        str(tier): {str(key): float(value) for key, value in thresholds.items()}
        for tier, thresholds in model_config.get("tier_thresholds", {}).items()
        if isinstance(thresholds, dict)
    }
    args.sleep_multipliers_by_tier = {
        str(tier): float(value)
        for tier, value in sleep.get("multipliers_by_tier", {}).items()
    }
    args.min_sleep_s = int(sleep.get("min_sleep_s", 3))
    args.max_sleep_s = int(sleep.get("max_sleep_s", 120))
    return args


if __name__ == "__main__":
    main()
