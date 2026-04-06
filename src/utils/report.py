from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from src.utils.constants import CATEGORY_STRATEGY_MAPPING


def format_signed_number(value: float, digits: int = 0) -> str:
    return f"{value:+,.{digits}f}"


def format_symbol_list(symbols: list[str]) -> str:
    if not symbols:
        return ""
    return " / ".join(symbols)


def build_category_lines(loss_df: pd.DataFrame) -> list[str]:
    lines = []

    for label, strategies in CATEGORY_STRATEGY_MAPPING.items():
        symbols = (
            loss_df[loss_df["strategy"].isin(strategies)]["mapped_symbol"]
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        lines.append(f"{label}: {format_symbol_list(symbols)}")
    # add a category for strategies that are not categorized in CATEGORY_STRATEGY_MAPPING
    categorized_strategies = set().union(*CATEGORY_STRATEGY_MAPPING.values())
    other_symbols = (
        loss_df[~loss_df["strategy"].isin(categorized_strategies)]["mapped_symbol"]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    lines.append(f"Other: {format_symbol_list(other_symbols)}")
    return lines


def format_report_table(df: pd.DataFrame, preferred_cols: list[str]) -> str:
    if df.empty:
        return "None"

    cols = [col for col in preferred_cols if col in df.columns]
    table_df = df[cols].copy() if cols else df.copy()

    if "npnl_r+un" in table_df.columns:
        table_df = table_df.sort_values("npnl_r+un")

    rename_map = {
        "base_strategy": "strategy",
        "mapped_symbol": "symbol",
        "volume_$": "vol",
        "npnl_r+un": "npnl",
        "npnl/volume_%": "npnl%",
    }
    table_df = table_df.rename(columns=rename_map)

    for col in ["vol", "npnl", "npnl%"]:
        if col in table_df.columns:
            table_df[col] = table_df[col].map(_format_metric_value)

    return "```text\n" + table_df.to_string(index=False) + "\n```"


def _format_metric_value(value: float) -> str:
    if pd.isna(value):
        return "-"
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    return f"{value:,.2f}"


def build_daily_report(
    total_npnl: float,
    severe_symbols: list[str],
    loss_symbols: list[str],
    loss_strats: pd.DataFrame,
    loss_sym_strats: pd.DataFrame,
) -> str:
    if severe_symbols:
        severe_line = f"Symbols with 24H NPNL < -3k: {format_symbol_list(severe_symbols)}"
    else:
        severe_line = "No symbol with 24H NPNL < -3k"

    if loss_symbols:
        loss_line = (
            f"[ {format_symbol_list(loss_symbols)} ] with loss of more than -1k "
            # TODO: "(Symbols in Blue are new listings)"
        )
    else:
        loss_line = "No symbol with loss of more than -1k"

    strat_table = format_report_table(
        loss_strats,
        ["base_strategy", "volume_$", "npnl_r+un", "npnl/volume_%"],
    )
    sym_strat_table = format_report_table(
        loss_sym_strats,
        ["mapped_symbol", "strategy", "name", "volume_$", "npnl_r+un", "npnl/volume_%"],
    )

    lines = [
        severe_line,
        "",
        f"Total NPNL: {format_signed_number(total_npnl)}",
        "",
        loss_line,
        "",
        "Losses mostly from -",
        *build_category_lines(loss_sym_strats),
        "",
        "Loss Strategies:",
        strat_table,
        "",
        "Loss Symbol Strategies:",
        sym_strat_table,
    ]
    return "\n".join(lines).strip() + "\n"


def save_report(report_text: str, output_dir: str | Path, prefix: str = "morning_report") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{prefix}_{timestamp}.txt"
    out_path.write_text(report_text, encoding="utf-8")
    return out_path
