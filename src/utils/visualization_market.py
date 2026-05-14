"""Market-specific chart renderers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils.visualization_shared import (
    format_axis_billions,
    format_axis_millions,
    format_axis_signed_thousands,
    format_axis_thousands,
    format_percent_value,
    format_price_value,
    format_ratio_percent,
    format_turnover_value,
    pad_axis,
    prepare_output_path,
    prepare_time_series_plot_df,
    ratio_fill_color,
    save_figure,
)


def etf_net_flows_to_png(
    flows_by_asset: dict[str, pd.DataFrame],
    output_path: str | Path,
    *,
    days: int = 8,
    figsize: tuple[float, float] = (11, 8),
    dpi: int = 140,
) -> Path:
    out_path = prepare_output_path(output_path)

    assets = [asset for asset in ("BTC", "ETH") if asset in flows_by_asset]
    if not assets:
        raise ValueError("flows_by_asset must include at least one of BTC or ETH.")

    fig, axes = plt.subplots(len(assets), 1, figsize=figsize, sharex=False)
    if len(assets) == 1:
        axes = [axes]

    for ax, asset in zip(axes, assets, strict=False):
        df = (
            flows_by_asset[asset]
            .loc[:, ["date", "total"]]
            .dropna(subset=["total"])
            .copy()
        )
        if df.empty:
            raise ValueError(f"{asset} ETF net flow data is empty.")
        df = df.sort_values(by="date").tail(days).reset_index(drop=True)
        values = df["total"].astype(float)
        colors = ["#4daa2c" if value >= 0 else "#d40000" for value in values]
        x = np.arange(len(df))
        bars = ax.bar(x, values, color=colors, width=0.32)

        ax.axhline(0, color="#d9d9d9", linewidth=0.8)
        ax.set_title(f"{asset} ETF Net Flows", fontsize=14, color="#666666", pad=8)
        ax.set_xticks(x)
        ax.set_xticklabels(
            [pd.Timestamp(date).strftime("%-d-%b-%y") for date in df["date"]],
            fontsize=9,
            color="#666666",
        )
        ax.tick_params(axis="y", colors="#666666", labelsize=9, length=0)
        ax.tick_params(axis="x", length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(False)

        value_range = max(abs(values.min()), abs(values.max()), 1.0)
        ax.set_ylim(
            values.min() - value_range * 0.25, values.max() + value_range * 0.25
        )
        for bar, value in zip(bars, values, strict=False):
            if value >= 0:
                y = value + value_range * 0.04
                va = "bottom"
            else:
                y = value - value_range * 0.06
                va = "top"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                y,
                f"{value:.1f}",
                ha="center",
                va=va,
                fontsize=9,
                color="#555555",
            )

    return save_figure(fig, out_path, dpi=dpi, tight_layout_h_pad=1.6)


def coinank_open_interest_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str = "BTC",
    days: int = 14,
    figsize: tuple[float, float] = (11, 3),
    dpi: int = 140,
) -> Path:
    out_path = prepare_output_path(output_path)
    plot_df = prepare_time_series_plot_df(
        df,
        required_cols=["date", "price", "open_interest_usd"],
        dropna_subset=["open_interest_usd"],
        days=days,
        column_context="open-interest",
        empty_message="Open-interest data is empty.",
    )

    x = np.arange(len(plot_df))
    oi = plot_df["open_interest_usd"].astype(float)
    price = plot_df["price"].astype(float)

    fig, ax_oi = plt.subplots(figsize=figsize)
    ax_price = ax_oi.twinx()

    ax_oi.fill_between(x, oi, color="#5da2ff", alpha=0.82, linewidth=0)
    ax_oi.plot(x, oi, color="#4c91f7", linewidth=1.2)
    ax_price.plot(x, price, color="#ff9b73", linewidth=1.0, alpha=0.9)

    ax_oi.set_xticks(x)
    ax_oi.set_xticklabels(
        [pd.Timestamp(date).strftime("%m-%d") for date in plot_df["date"]],
        fontsize=8,
        color="#777777",
    )
    ax_oi.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: format_axis_billions(value))
    )
    ax_price.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: format_axis_thousands(value))
    )
    ax_oi.tick_params(axis="y", colors="#777777", labelsize=8, length=0)
    ax_price.tick_params(axis="y", colors="#777777", labelsize=8, length=0)
    ax_oi.tick_params(axis="x", length=0)
    ax_oi.grid(axis="y", linestyle="--", linewidth=0.5, color="#e5e5e5", alpha=0.9)
    ax_oi.grid(axis="x", visible=False)

    oi_min = oi.min()
    oi_max = oi.max()
    oi_pad = max((oi_max - oi_min) * 0.25, oi_max * 0.02)
    ax_oi.set_ylim(max(0, oi_min - oi_pad), oi_max + oi_pad)

    price_min = price.min()
    price_max = price.max()
    price_pad = max((price_max - price_min) * 0.25, price_max * 0.01)
    ax_price.set_ylim(max(0, price_min - price_pad), price_max + price_pad)

    for spine in ax_oi.spines.values():
        spine.set_visible(False)
    for spine in ax_price.spines.values():
        spine.set_visible(False)

    price_handle = plt.Line2D(
        [0],
        [0],
        color="#ff9b73",
        marker="o",
        markerfacecolor="white",
        markersize=4,
        linewidth=1.0,
        label=f"{base_asset.upper()} Price",
    )
    oi_handle = plt.Line2D(
        [0],
        [0],
        color="#4c91f7",
        marker="o",
        markerfacecolor="white",
        markersize=4,
        linewidth=1.2,
        label="OI",
    )
    ax_price.legend(
        handles=[price_handle, oi_handle],
        loc="upper right",
        frameon=False,
        fontsize=7,
        ncol=2,
        handlelength=1.2,
        handletextpad=0.3,
    )

    ax_oi.text(
        0.95,
        0.12,
        "CoinAnk",
        transform=ax_oi.transAxes,
        ha="right",
        va="center",
        fontsize=11,
        color="#9aa0a6",
        alpha=0.75,
        fontweight="bold",
    )

    return save_figure(fig, out_path, dpi=dpi, tight_layout_pad=0.5)


def binance_perp_open_interest_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str,
    days: int = 30,
    figsize: tuple[float, float] = (11, 2.5),
    dpi: int = 180,
) -> Path:
    out_path = prepare_output_path(output_path)
    plot_df = prepare_time_series_plot_df(
        df,
        required_cols=["date", "open_interest", "open_interest_value"],
        dropna_subset=["open_interest"],
        days=days,
        column_context="open-interest",
        empty_message="Binance perp open-interest data is empty.",
    )

    x = np.arange(len(plot_df))
    open_interest = plot_df["open_interest"].astype(float)
    open_interest_value = plot_df["open_interest_value"].astype(float)

    fig, ax_oi = plt.subplots(figsize=figsize)
    ax_value = ax_oi.twinx()

    ax_oi.bar(
        x,
        open_interest,
        color="#f6c31a",
        width=0.18,
        label=f"Open Interest ({base_asset.upper()})",
        zorder=3,
    )
    ax_value.plot(
        x,
        open_interest_value,
        color="#8a8a8a",
        marker="o",
        markersize=2.4,
        linewidth=1.0,
        label="Notional Value of Open Interest (USDT)",
        zorder=4,
    )

    _style_binance_perp_axes(ax_oi, ax_value, plot_df)
    ax_oi.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: format_axis_millions(value))
    )
    ax_value.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: format_axis_millions(value))
    )
    pad_axis(ax_oi, open_interest)
    pad_axis(ax_value, open_interest_value)

    handles_oi, labels_oi = ax_oi.get_legend_handles_labels()
    handles_value, labels_value = ax_value.get_legend_handles_labels()
    ax_oi.legend(
        handles_oi + handles_value,
        labels_oi + labels_value,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.32),
        frameon=False,
        fontsize=7,
        ncol=2,
        handlelength=1.2,
        columnspacing=1.0,
    )

    ax_oi.text(
        0.0,
        1.08,
        "Open Interest",
        transform=ax_oi.transAxes,
        fontsize=9,
        fontweight="bold",
    )
    ax_oi.text(
        0.0, 0.94, "Single", transform=ax_oi.transAxes, fontsize=7, color="#555555"
    )

    return save_figure(fig, out_path, dpi=dpi, tight_layout_pad=0.4)


def binance_perp_taker_buy_sell_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str,
    days: int = 30,
    figsize: tuple[float, float] = (11, 2.5),
    dpi: int = 180,
) -> Path:
    out_path = prepare_output_path(output_path)
    plot_df = prepare_time_series_plot_df(
        df,
        required_cols=["date", "buy_volume", "sell_volume"],
        dropna_subset=["buy_volume", "sell_volume"],
        days=days,
        column_context="taker volume",
        empty_message="Binance perp taker volume data is empty.",
    )

    x = np.arange(len(plot_df))
    buy_volume = plot_df["buy_volume"].astype(float)
    sell_volume = plot_df["sell_volume"].astype(float)
    width = 0.18

    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(
        x - width / 2,
        sell_volume,
        color="#f04d5e",
        width=width,
        label=f"Taker Sell Volume ({base_asset.upper()})",
        zorder=3,
    )
    ax.bar(
        x + width / 2,
        buy_volume,
        color="#2fc98f",
        width=width,
        label=f"Taker Buy Volume ({base_asset.upper()})",
        zorder=3,
    )

    _style_binance_perp_axes(ax, None, plot_df)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: format_axis_millions(value))
    )
    pad_axis(ax, pd.concat([buy_volume, sell_volume], ignore_index=True))
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.32),
        frameon=False,
        fontsize=7,
        ncol=2,
        handlelength=1.2,
        columnspacing=1.0,
    )
    ax.text(
        0.0,
        1.08,
        "Taker Buy/Sell Volume",
        transform=ax.transAxes,
        fontsize=9,
        fontweight="bold",
    )

    return save_figure(fig, out_path, dpi=dpi, tight_layout_pad=0.4)


def coinmarketcap_liquidations_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str,
    days: int = 14,
    figsize: tuple[float, float] = (11, 4.3),
    dpi: int = 180,
) -> Path:
    out_path = prepare_output_path(output_path)
    plot_df = prepare_time_series_plot_df(
        df,
        required_cols=[
            "date",
            "long_liquidation_usd",
            "short_liquidation_usd",
            "price_usd",
        ],
        dropna_subset=["date"],
        days=days,
        column_context="CoinMarketCap liquidation",
        empty_message="CoinMarketCap liquidation chart data is empty.",
        normalize_dates_utc=True,
    )

    x = np.arange(len(plot_df))
    long_liquidation = (
        plot_df["long_liquidation_usd"].fillna(0.0).astype(float).clip(lower=0.0)
    )
    short_liquidation = -(
        plot_df["short_liquidation_usd"].fillna(0.0).astype(float).clip(lower=0.0)
    )
    price = plot_df["price_usd"].astype(float)

    fig, ax_liq = plt.subplots(figsize=figsize)
    ax_price = ax_liq.twinx()

    short_bars = ax_liq.bar(
        x,
        short_liquidation,
        color="#f43f4d",
        width=0.92,
        label="Short",
        zorder=3,
    )
    long_bars = ax_liq.bar(
        x,
        long_liquidation,
        color="#18b7a0",
        width=0.92,
        label="Long",
        zorder=3,
    )
    price_line = ax_price.plot(
        x,
        price,
        color="#f0b528",
        linewidth=1.15,
        label=f"{base_asset.upper()} Price",
        zorder=4,
    )[0]

    _style_binance_perp_axes(ax_liq, ax_price, plot_df)
    ax_liq.axhline(0, color="#dddddd", linewidth=0.9, zorder=1)
    ax_liq.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: format_axis_signed_thousands(value))
    )
    liq_limit = max(
        float(long_liquidation.max()) if not long_liquidation.empty else 0.0,
        float(short_liquidation.abs().max()) if not short_liquidation.empty else 0.0,
        1.0,
    )
    ax_liq.set_ylim(-liq_limit * 1.15, liq_limit * 1.15)
    pad_axis(ax_price, price)
    ax_price.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: f"${value:0.4f}")
    )

    ax_liq.legend(
        [short_bars, long_bars, price_line],
        ["Short", "Long", f"{base_asset.upper()} Price"],
        loc="upper center",
        bbox_to_anchor=(0.52, 1.02),
        frameon=False,
        fontsize=7,
        ncol=3,
        handlelength=1.0,
        handletextpad=0.35,
        columnspacing=1.1,
    )
    ax_liq.text(
        0.0,
        1.07,
        f"{base_asset.upper()} Total Liquidations Chart",
        transform=ax_liq.transAxes,
        fontsize=9,
        fontweight="bold",
    )
    ax_liq.text(
        0.985,
        0.11,
        "CoinMarketCap",
        transform=ax_liq.transAxes,
        ha="right",
        va="center",
        fontsize=11,
        color="#b8b8b8",
        alpha=0.9,
        fontweight="bold",
    )

    return save_figure(fig, out_path, dpi=dpi, tight_layout_pad=0.5)


def coinank_long_short_realtime_to_png(
    summary: Any,
    output_path: str | Path,
    *,
    figsize: tuple[float, float] = (11, 2.1),
    dpi: int = 180,
) -> Path:
    out_path = prepare_output_path(output_path)

    headers = [
        "Symbol",
        "Price",
        "24H (%)",
        "Long(5m)",
        "Short(5m)",
        "Long(30m)",
        "Short(30m)",
        "Long(1h)",
        "Short(1h)",
        "Long(4h)",
        "Short(4h)",
    ]
    intervals = [
        ("long_5m", "long"),
        ("long_5m", "short"),
        ("long_30m", "long"),
        ("long_30m", "short"),
        ("long_1h", "long"),
        ("long_1h", "short"),
        ("long_4h", "long"),
        ("long_4h", "short"),
    ]
    widths = [1.6, 1.25, 1.25, 1.45, 1.45, 1.45, 1.45, 1.45, 1.45, 1.45, 1.45]
    total_width = float(sum(widths))

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, total_width)
    ax.set_ylim(0, 2.3)
    ax.axis("off")

    header_y = 1.55
    row_y = 0.55
    row_height = 0.72

    x_left = 0.0
    for header, width in zip(headers, widths, strict=False):
        ax.text(
            x_left + width / 2,
            header_y + 0.45,
            header,
            ha="center",
            va="center",
            fontsize=7.2,
            color="#555555",
            fontweight="bold",
        )
        x_left += width

    x_left = 0.0
    base_asset = str(getattr(summary, "base_asset", "")).upper()
    price = format_price_value(getattr(summary, "price", None))
    price_change = format_percent_value(getattr(summary, "price_change_24h", None))
    base_values = [base_asset, price, price_change]

    raw_price_change = getattr(summary, "price_change_24h", None)
    for value, width in zip(base_values, widths[:3], strict=False):
        facecolor = "white"
        if value == price_change and isinstance(raw_price_change, (int, float)):
            facecolor = ratio_fill_color(
                0.6 if float(raw_price_change) >= 0 else 0.4,
                positive=float(raw_price_change) >= 0,
            )
        ax.add_patch(
            plt.Rectangle(
                (x_left, row_y),
                width,
                row_height,
                facecolor=facecolor,
                edgecolor="#ececec",
                linewidth=0.6,
            )
        )
        ax.text(
            x_left + width / 2,
            row_y + row_height / 2,
            value,
            ha="center",
            va="center",
            fontsize=8.8,
            color="#222222",
            fontweight="bold" if value == base_asset else "normal",
        )
        x_left += width

    for (attr_name, side), width in zip(intervals, widths[3:], strict=False):
        interval_summary = getattr(summary, attr_name)
        turnover = (
            getattr(interval_summary, "long_turnover")
            if side == "long"
            else getattr(interval_summary, "short_turnover")
        )
        ratio = (
            getattr(interval_summary, "long_ratio")
            if side == "long"
            else getattr(interval_summary, "short_ratio")
        )
        facecolor = ratio_fill_color(ratio, positive=(side == "long"))
        ax.add_patch(
            plt.Rectangle(
                (x_left, row_y),
                width,
                row_height,
                facecolor=facecolor,
                edgecolor="#ececec",
                linewidth=0.6,
            )
        )
        ax.text(
            x_left + width / 2,
            row_y + row_height * 0.62,
            format_turnover_value(turnover),
            ha="center",
            va="center",
            fontsize=8.2,
            color="#222222",
            fontweight="bold",
        )
        ax.text(
            x_left + width / 2,
            row_y + row_height * 0.26,
            format_ratio_percent(ratio),
            ha="center",
            va="center",
            fontsize=7.4,
            color="#555555",
        )
        x_left += width

    return save_figure(fig, out_path, dpi=dpi, tight_layout_pad=0.25)


def _style_binance_perp_axes(
    ax: plt.Axes,
    secondary_ax: plt.Axes | None,
    plot_df: pd.DataFrame,
) -> None:
    x = np.arange(len(plot_df))
    tick_step = max(int(np.ceil(len(plot_df) / 12)), 1)
    tick_positions = x[::tick_step]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(
        [
            pd.Timestamp(date).strftime("%m/%d")
            for date in plot_df.loc[tick_positions, "date"]
        ],
        fontsize=7,
        color="#9a9a9a",
    )
    ax.tick_params(axis="x", length=0)
    ax.tick_params(axis="y", colors="#9a9a9a", labelsize=7, length=0)
    ax.grid(axis="y", color="#ececec", linewidth=0.7)
    ax.grid(axis="x", visible=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    if secondary_ax is not None:
        secondary_ax.tick_params(axis="y", colors="#9a9a9a", labelsize=7, length=0)
        for spine in secondary_ax.spines.values():
            spine.set_visible(False)
