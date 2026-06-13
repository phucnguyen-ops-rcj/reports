from __future__ import annotations

from src.clients.third_parties.coingecko import GlobalMarketSummary
from src.utils.constants import CATEGORY_STRATEGY_MAPPING, THRESHOLDS
from src.settings import app_settings
import pandas as pd
from datetime import datetime
import pytz


def format_signed_number(value: float, digits: int = 0) -> str:
    return f"{value:+,.{digits}f}"


def format_symbol_list(symbols: list[str]) -> str:
    if not symbols:
        return ""
    return " / ".join(symbols)


def build_category_lines(loss_df: pd.DataFrame) -> str:
    lines = ["Losses mostly from -"]

    for cat, strats in CATEGORY_STRATEGY_MAPPING.items():
        symbols = (
            loss_df[loss_df["strategy"].isin(strats)]["mapped_symbol"]
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        lines.append(f"{cat}: {format_symbol_list(symbols)}")
    # add a category for strategies that are not categorized in STRATEGY_CATEGORY_MAPPING
    categorized_strategies = set().union(*CATEGORY_STRATEGY_MAPPING.values())
    other_symbols = (
        loss_df[~loss_df["strategy"].isin(categorized_strategies)]["mapped_symbol"]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    lines.append(f"Undefined: {format_symbol_list(other_symbols)}")
    return "\n".join(lines)


def format_report_table(df: pd.DataFrame, preferred_cols: list[str]) -> str:
    if df.empty:
        return "None"

    cols = [col for col in preferred_cols if col in df.columns]
    table_df = df.loc[:, cols].copy() if cols else df.copy()

    if "npnl_r+un" in table_df.columns:
        table_df = table_df.sort_values("npnl_r+un")

    return table_df.to_string(
        index=False, justify="left", float_format=_format_metric_value
    )


def _format_metric_value(value: float) -> str:
    if pd.isna(value):
        return "-"
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    return f"{value:,.2f}"


def format_usd_millions(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "***"
    return f"{value / 1_000_000:.1f}"


def build_alt_market_summary_sentence(
    symbol: str,
    *,
    spot_volume_24h: float | None,
    binance_perp_volume_24h: float | None,
    bybit_perp_volume_24h: float | None,
) -> str:
    symbol = symbol.upper()
    return (
        f"In the past 24H, {symbol} traded average spot volume of "
        f"~${format_usd_millions(spot_volume_24h)}mm. Binance perp recorded "
        f"trading volume of ~${format_usd_millions(binance_perp_volume_24h)}mm "
        f"and Bybit perp ~${format_usd_millions(bybit_perp_volume_24h)}mm "
        "over the past 24H."
    )


def build_daily_report(
    total_npnl: float,
    loss_base_strats: list[str],
    severe_symbols: list[str],
    large_profit_symbols: list[str],
    loss_symbols: list[str],
    loss_sym_strats: pd.DataFrame,
) -> str:
    large_profit_threshold_k = THRESHOLDS["large_profit_pnl"] / 1000
    large_profit_label = f"+{large_profit_threshold_k:g}k"

    if severe_symbols:
        severe_line = (
            f"Symbols with 24H NPNL < -3k: {format_symbol_list(severe_symbols)}"
        )
    else:
        severe_line = "No symbol with 24H NPNL < -3k"

    if large_profit_symbols:
        large_profit_line = (
            f"Symbols with 24H NPNL > {large_profit_label}: "
            f"{format_symbol_list(large_profit_symbols)}"
        )
    else:
        large_profit_line = f"No symbol with 24H NPNL > {large_profit_label}"

    if loss_base_strats:
        loss_strat_line = (
            f"[ {format_symbol_list(loss_base_strats)} ] with loss of more than -1k "
        )
    else:
        loss_strat_line = "No strategy with loss of more than -1k"

    if loss_symbols:
        loss_line = (
            f"[ {format_symbol_list(loss_symbols)} ] with loss of more than -1k "
            # TODO: "(Symbols in Blue are new listings)"
        )
    else:
        loss_line = "No symbol with loss of more than -1k"

    category_lines = (
        build_category_lines(loss_sym_strats) if not loss_sym_strats.empty else ""
    )

    lines = [
        "",
        f"Total NPNL: {format_signed_number(total_npnl)}",
        "",
        severe_line,
        "",
        large_profit_line,
        "",
        loss_strat_line,
        "",
        loss_line,
        "",
        category_lines,
    ]
    return "\n".join(lines).strip() + "\n"


def build_market_summary_report(market_summary: GlobalMarketSummary) -> str:
    if not market_summary:
        return "No market summary data available."

    total_market_cap = market_summary.total_market_cap_usd
    total_volume = market_summary.total_volume_usd
    market_cap_change_24h = market_summary.market_cap_change_percentage_24h_usd

    sg_tz = pytz.timezone(app_settings.tz)  # or datetime.timezone(timedelta(hours=8))
    _now = market_summary.updated_at or datetime.now(sg_tz).timestamp()
    lines = [
        f"Market Summary at {datetime.fromtimestamp(_now, tz=sg_tz).strftime('%Y-%m-%d %H:%M:%S')} (SGT):",
        f"  - Total Market Cap: ${total_market_cap:,.2f}",
        f"  - Market Cap Change (24H): {market_cap_change_24h:+.2f}%",
        f"  - Total 24H Volume: ${total_volume:,.2f}",
    ]
    return "\n".join(lines)
