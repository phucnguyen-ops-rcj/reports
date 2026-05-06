"""Utility functions for converting DataFrames to visualization formats."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb


def _normalize_sizes(sizes: list[float], width: float, height: float) -> list[float]:
    total = sum(sizes)
    if total <= 0:
        return []
    scale = width * height / total
    return [size * scale for size in sizes]


def _worst_ratio(row: list[float], side: float) -> float:
    if not row or side <= 0:
        return float("inf")
    row_sum = sum(row)
    if row_sum <= 0:
        return float("inf")
    return max(
        (side * side * max(row)) / (row_sum * row_sum),
        (row_sum * row_sum) / (side * side * min(row)),
    )


def _layout_row(
    row: list[float],
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[dict[str, float]]:
    rects: list[dict[str, float]] = []
    row_sum = sum(row)
    if row_sum <= 0:
        return rects

    if width >= height:
        row_width = row_sum / height
        current_y = y
        for size in row:
            rect_height = size / row_width
            rects.append({"x": x, "y": current_y, "dx": row_width, "dy": rect_height})
            current_y += rect_height
    else:
        row_height = row_sum / width
        current_x = x
        for size in row:
            rect_width = size / row_height
            rects.append({"x": current_x, "y": y, "dx": rect_width, "dy": row_height})
            current_x += rect_width
    return rects


def _squarify(
    sizes: list[float],
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[dict[str, float]]:
    remaining = [size for size in sizes if size > 0]
    rects: list[dict[str, float]] = []
    row: list[float] = []

    while remaining:
        size = remaining[0]
        side = min(width, height)
        if not row or _worst_ratio([*row, size], side) <= _worst_ratio(row, side):
            row.append(size)
            remaining.pop(0)
            continue

        rects.extend(_layout_row(row, x, y, width, height))
        row_sum = sum(row)
        if width >= height:
            row_width = row_sum / height
            x += row_width
            width -= row_width
        else:
            row_height = row_sum / width
            y += row_height
            height -= row_height
        row = []

    rects.extend(_layout_row(row, x, y, width, height))
    return rects


def _market_change_color(
    change: float | None, max_abs_change: float
) -> tuple[float, float, float]:
    if change is None or pd.isna(change):
        return to_rgb("#9aa0a6")

    intensity = min(abs(float(change)) / max_abs_change, 1.0)
    if change >= 0:
        low = np.array(to_rgb("#6fa35f"))
        high = np.array(to_rgb("#2e7d32"))
    else:
        low = np.array(to_rgb("#c85252"))
        high = np.array(to_rgb("#9f2f2f"))
    return tuple(low + (high - low) * intensity)


def _format_heatmap_price(value: float) -> str:
    if value >= 1000:
        return f"${value:,.2f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:,.4f}"


def _heatmap_label(
    *,
    base_asset: str,
    price: float | None,
    change: float | None,
    rect: dict[str, float],
) -> tuple[str, float, str]:
    min_side = min(rect["dx"], rect["dy"])
    area = rect["dx"] * rect["dy"]
    change_text = "-" if change is None or pd.isna(change) else f"{float(change):+.2f}%"
    price_text = (
        "" if price is None or pd.isna(price) else _format_heatmap_price(float(price))
    )

    if area >= 240 and min_side >= 8:
        return (
            f"{base_asset}\n{price_text}\n{change_text}",
            min(24, max(8, min_side * 0.9)),
            "bold",
        )
    if area >= 38 and min_side >= 3.8:
        return (
            f"{base_asset}\n{change_text}",
            min(10, max(3.5, min_side * 0.85)),
            "bold",
        )
    if area >= 12 and min_side >= 1.8:
        return base_asset, min(6, max(2.5, min_side * 0.9)), "bold"
    return base_asset[:4], min(4, max(1.8, min_side * 0.95)), "bold"


def _rebalance_treemap_area(
    df: pd.DataFrame,
    *,
    area_col: str,
    anchor_asset: str,
    anchor_share: float,
) -> pd.Series:
    weights = df[area_col].astype(float).copy()
    anchor_mask = df["base_asset"].astype(str).str.upper() == anchor_asset.upper()
    other_mask = ~anchor_mask
    if not anchor_mask.any() or not other_mask.any():
        return weights

    anchor_share = min(max(anchor_share, 0.0), 1.0)
    other_total = weights[other_mask].sum()
    if other_total <= 0:
        return weights

    weights.loc[anchor_mask] = anchor_share
    weights.loc[other_mask] = (weights.loc[other_mask] / other_total) * (
        1 - anchor_share
    )
    return weights


def _apply_treemap_area_groups(
    df: pd.DataFrame,
    *,
    area_col: str,
    area_groups: dict[str, float] | None,
) -> pd.Series:
    weights = df[area_col].astype(float).copy()
    if not area_groups:
        return weights

    allocated = pd.Series(False, index=df.index)
    grouped_weights = pd.Series(0.0, index=df.index)
    normalized_assets = df["base_asset"].astype(str).str.upper()
    remaining_share = 1.0

    for group_assets, group_share in area_groups.items():
        assets = {
            asset.strip().upper() for asset in group_assets.split(",") if asset.strip()
        }
        if not assets:
            continue

        group_mask = normalized_assets.isin(assets) & ~allocated
        if not group_mask.any():
            continue

        group_share = min(max(group_share, 0.0), remaining_share)
        group_total = weights[group_mask].sum()
        if group_total <= 0:
            continue

        grouped_weights.loc[group_mask] = (
            weights.loc[group_mask] / group_total
        ) * group_share
        allocated.loc[group_mask] = True
        remaining_share -= group_share
        if remaining_share <= 0:
            break

    remaining_mask = ~allocated
    remaining_total = weights[remaining_mask].sum()
    if remaining_total > 0 and remaining_share > 0:
        grouped_weights.loc[remaining_mask] = (
            weights.loc[remaining_mask] / remaining_total
        ) * remaining_share

    return grouped_weights.where(grouped_weights > 0, weights)


def _grouped_treemap_rects(
    df: pd.DataFrame,
    *,
    area_col: str,
    area_groups: dict[str, float],
    width: float,
    height: float,
) -> list[tuple[int, dict[str, float]]]:
    rects: list[tuple[int, dict[str, float]]] = []
    allocated = pd.Series(False, index=df.index)
    normalized_assets = df["base_asset"].astype(str).str.upper()
    current_x = 0.0

    for group_assets, group_share in area_groups.items():
        assets = {
            asset.strip().upper() for asset in group_assets.split(",") if asset.strip()
        }
        group_mask = normalized_assets.isin(assets) & ~allocated
        if not group_mask.any() or group_share <= 0:
            continue

        group_width = width * group_share
        group_df = df.loc[group_mask].sort_values(by=area_col, ascending=False)
        group_sizes = _normalize_sizes(
            group_df[area_col].astype(float).tolist(),
            group_width,
            height,
        )
        group_rects = _squarify(group_sizes, current_x, 0.0, group_width, height)
        rects.extend(zip(group_df.index.tolist(), group_rects, strict=False))
        allocated.loc[group_df.index] = True
        current_x += group_width

    remaining_df = df.loc[~allocated].sort_values(by=area_col, ascending=False)
    remaining_width = max(width - current_x, 0.0)
    if not remaining_df.empty and remaining_width > 0:
        remaining_sizes = _normalize_sizes(
            remaining_df[area_col].astype(float).tolist(),
            remaining_width,
            height,
        )
        remaining_rects = _squarify(
            remaining_sizes, current_x, 0.0, remaining_width, height
        )
        rects.extend(zip(remaining_df.index.tolist(), remaining_rects, strict=False))

    return rects


def _format_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Format numeric columns with comma separators (e.g. 1000000 → 1,000,000.00)."""
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and df[col].dtype != bool:
            df[col] = df[col].apply(
                lambda x: f"{x:,.2f}"
                if isinstance(x, (int, float)) and np.isfinite(x)
                else x
            )
    return df


def crypto_market_heatmap_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    title: str = "",
    max_abs_change: float = 5.0,
    top_n: int = 50,
    grid_columns: int = 10,
    figsize: tuple[float, float] = (16, 8),
    dpi: int = 220,
    area_groups: dict[str, float] | None = None,
) -> Path:
    """Render the public crypto heatmap as a variable-area treemap.

    ``grid_columns`` is kept for backward compatibility with the old seaborn
    grid renderer and is intentionally ignored.
    """
    _ = grid_columns
    return crypto_market_treemap_to_png(
        df,
        output_path,
        title=title,
        max_abs_change=max_abs_change,
        top_n=top_n,
        figsize=figsize,
        dpi=dpi,
        area_groups=area_groups,
    )


def crypto_market_treemap_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    title: str = "",
    max_abs_change: float = 5.0,
    top_n: int | None = None,
    figsize: tuple[float, float] = (16, 8),
    dpi: int = 220,
    area_groups: dict[str, float] | None = None,
) -> Path:
    """Render a crypto market treemap sized by market cap or volume and colored by 24H change."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    area_col = "market_cap" if "market_cap" in df.columns else "quote_volume"
    required_cols = ["base_asset", "last_price", "price_change_percent", area_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing heatmap columns: {', '.join(missing_cols)}")

    plot_df = df.loc[:, required_cols].dropna(subset=[area_col]).copy()
    plot_df = plot_df[plot_df[area_col] > 0]
    if plot_df.empty:
        raise ValueError("Heatmap data is empty.")

    plot_df = plot_df.sort_values(by=area_col, ascending=False).reset_index(drop=True)
    if top_n is not None:
        plot_df = plot_df.head(top_n).reset_index(drop=True)
    resolved_area_groups = area_groups or {
        "BTC": 0.25,
        "ETH,BNB,XRP,SOL": 0.2,
    }
    rects = _grouped_treemap_rects(
        plot_df,
        area_col=area_col,
        area_groups=resolved_area_groups,
        width=100.0,
        height=60.0,
    )

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")
    ax.invert_yaxis()

    for row_index, rect in rects:
        row = plot_df.loc[row_index]
        change = row["price_change_percent"]
        color = _market_change_color(change, max_abs_change)
        patch = plt.Rectangle(
            (rect["x"], rect["y"]),
            rect["dx"],
            rect["dy"],
            facecolor=color,
            edgecolor="#3f6138",
            linewidth=0.5,
        )
        ax.add_patch(patch)

        base_asset = str(row["base_asset"])
        price = row["last_price"]
        label, font_size, fontweight = _heatmap_label(
            base_asset=base_asset,
            price=None if pd.isna(price) else float(price),
            change=None if pd.isna(change) else float(change),
            rect=rect,
        )
        text = ax.text(
            rect["x"] + rect["dx"] / 2,
            rect["y"] + rect["dy"] / 2,
            label,
            ha="center",
            va="center",
            color="white",
            fontsize=font_size,
            fontweight=fontweight,
            linespacing=0.9,
            clip_on=True,
        )
        text.set_clip_path(patch)

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=10)

    plt.tight_layout()
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def etf_net_flows_to_png(
    flows_by_asset: dict[str, pd.DataFrame],
    output_path: str | Path,
    *,
    days: int = 8,
    figsize: tuple[float, float] = (11, 8),
    dpi: int = 140,
) -> Path:
    """Render Farside ETF net flow bar charts for BTC/ETH-style daily totals."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

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

    plt.tight_layout(h_pad=1.6)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def _format_axis_billions(value: float) -> str:
    return f"${value / 1_000_000_000:.2f}B"


def _format_axis_thousands(value: float) -> str:
    return f"${value / 1_000:.2f}K"


def coinank_open_interest_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str = "BTC",
    days: int = 14,
    figsize: tuple[float, float] = (11, 3),
    dpi: int = 140,
) -> Path:
    """Render CoinAnk open-interest area chart with price line overlay."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    required_cols = ["date", "price", "open_interest_usd"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing open-interest columns: {', '.join(missing_cols)}")

    plot_df = df.loc[:, required_cols].dropna(subset=["open_interest_usd"]).copy()
    plot_df = plot_df.sort_values(by="date").tail(days).reset_index(drop=True)
    if plot_df.empty:
        raise ValueError("Open-interest data is empty.")

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
        plt.FuncFormatter(lambda value, _: _format_axis_billions(value))
    )
    ax_price.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: _format_axis_thousands(value))
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

    plt.tight_layout(pad=0.5)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def binance_perp_open_interest_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str,
    days: int = 30,
    figsize: tuple[float, float] = (11, 2.5),
    dpi: int = 180,
) -> Path:
    """Render Binance perp open interest and notional open interest history."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    required_cols = ["date", "open_interest", "open_interest_value"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing open-interest columns: {', '.join(missing_cols)}")

    plot_df = df.loc[:, required_cols].dropna(subset=["open_interest"]).copy()
    plot_df = plot_df.sort_values(by="date").tail(days).reset_index(drop=True)
    if plot_df.empty:
        raise ValueError("Binance perp open-interest data is empty.")

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
        plt.FuncFormatter(lambda value, _: _format_axis_millions(value))
    )
    ax_value.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _: _format_axis_millions(value))
    )
    _pad_axis(ax_oi, open_interest)
    _pad_axis(ax_value, open_interest_value)

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

    plt.tight_layout(pad=0.4)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def binance_perp_taker_buy_sell_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str,
    days: int = 30,
    figsize: tuple[float, float] = (11, 2.5),
    dpi: int = 180,
) -> Path:
    """Render Binance perp taker buy/sell volume history."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    required_cols = ["date", "buy_volume", "sell_volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing taker volume columns: {', '.join(missing_cols)}")

    plot_df = (
        df.loc[:, required_cols].dropna(subset=["buy_volume", "sell_volume"]).copy()
    )
    plot_df = plot_df.sort_values(by="date").tail(days).reset_index(drop=True)
    if plot_df.empty:
        raise ValueError("Binance perp taker volume data is empty.")

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
        plt.FuncFormatter(lambda value, _: _format_axis_millions(value))
    )
    _pad_axis(ax, pd.concat([buy_volume, sell_volume], ignore_index=True))
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

    plt.tight_layout(pad=0.4)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


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


def _pad_axis(ax: plt.Axes, values: pd.Series) -> None:
    finite_values = values[np.isfinite(values)]
    if finite_values.empty:
        return
    max_value = float(finite_values.max())
    min_value = min(float(finite_values.min()), 0.0)
    pad = max((max_value - min_value) * 0.18, max_value * 0.05, 1.0)
    ax.set_ylim(min_value, max_value + pad)


def _format_axis_millions(value: float) -> str:
    return f"{value / 1_000_000:,.0f}M"


def net_pnl_to_png_styled(
    df: pd.DataFrame,
    output_path: str | Path,
    title: str = "",
    highlight_col: str | None = None,
    cmap: str = "RdYlGn",
) -> Path:
    """Convert DataFrame to PNG with conditional formatting/highlighting.

    Args:
        df: DataFrame to convert
        output_path: Path to save PNG file
        title: Optional title for the image
        highlight_col: Column name to highlight (numeric values)
        cmap: Colormap for highlighting (e.g., 'RdYlGn', 'RdYlBu')

    Returns:
        Path to saved PNG file
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df_display = _format_numeric_columns(df.copy().round(2))
    # for col in df_display.columns:
    #     if pd.api.types.is_numeric_dtype(df_display[col]):
    #         df_display[col] = df_display[col].apply(
    #             lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and np.isfinite(x) else x
    #         )

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.axis("tight")
    ax.axis("off")

    # Prepare cell colors - initialize with white
    color_array = np.ones((len(df_display), len(df_display.columns), 3))

    # Highlight total row by name - stronger blue
    if "strategy" in df_display.columns:
        total_mask = df_display["strategy"] == "Total"
        color_array[total_mask.values, :] = [0.7, 0.9, 1.0]

    # Highlight rows where npnl_r+un < -1000 - light red
    if "npnl_r+un" in df.columns:
        for i, val in enumerate(df["npnl_r+un"]):
            if isinstance(val, (int, float)) and val < -1000:
                color_array[i, :] = [1.0, 0.85, 0.85]

    table = ax.table(
        cellText=df_display.values,
        colLabels=df_display.columns,
        cellLoc="left",
        loc="center",
        cellColours=color_array,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)

    # Style header
    for i in range(len(df_display.columns)):
        table[(0, i)].set_facecolor("#2c3e50")
        table[(0, i)].set_text_props(weight="bold", color="white")

    if title:
        plt.title(title, fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()
    plt.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)

    return out_path


def trading_volume_to_png_styled(
    df: pd.DataFrame, output_path: str | Path, title: str = ""
) -> Path:
    """Convert trading volume DataFrame to PNG, highlighting rows that do not meet the requirement.

    Args:
        df: DataFrame to convert (must contain a boolean 'meets_requirement' column)
        output_path: Path to save PNG file
        title: Optional title for the image

    Returns:
        Path to saved PNG file
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df_display = _format_numeric_columns(df.copy().round(2))

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.axis("tight")
    ax.axis("off")

    # Prepare cell colors — white by default, light red for rows that miss the requirement
    color_array = np.ones((len(df_display), len(df_display.columns), 3))
    if "meets_requirement" in df_display.columns:
        for i, meets in enumerate(df_display["meets_requirement"]):
            if not meets:
                color_array[i, :] = [1.0, 0.85, 0.85]  # light red for failing rows

    table = ax.table(
        cellText=df_display.values,
        colLabels=df_display.columns,
        cellLoc="left",
        loc="center",
        cellColours=color_array,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)

    # Style header
    for i in range(len(df_display.columns)):
        table[(0, i)].set_facecolor("#2c3e50")
        table[(0, i)].set_text_props(weight="bold", color="white")

    if title:
        plt.title(title, fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()
    plt.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)

    return out_path
