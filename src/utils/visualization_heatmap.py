"""Treemap and heatmap visualization helpers."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.utils.visualization_shared import (
    ECHARTS_JS,
    PYECHARTS_ASSET_DIR,
    ensure_required_columns,
    format_heatmap_price,
    logger,
    market_change_color,
    prepare_output_path,
    save_figure,
)

try:
    from pyecharts import options as opts
    from pyecharts.charts import TreeMap
    from pyecharts.commons.utils import JsCode
    from pyecharts.globals import CurrentConfig
    from pyecharts.render import make_snapshot
    from snapshot_selenium import snapshot
except Exception:  # pragma: no cover
    opts = None
    TreeMap = None
    JsCode = None
    CurrentConfig = None
    make_snapshot = None
    snapshot = None


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
        "" if price is None or pd.isna(price) else format_heatmap_price(float(price))
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
    _ = grid_columns
    try:
        return _crypto_market_treemap_to_png_echarts(
            df,
            output_path,
            title=title,
            max_abs_change=max_abs_change,
            top_n=top_n,
            figsize=figsize,
            dpi=dpi,
            area_groups=area_groups,
        )
    except Exception:
        logger.warning(
            "Falling back to Matplotlib heatmap renderer after pyecharts export failed.",
            exc_info=True,
        )
        return _crypto_market_treemap_to_png_matplotlib(
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
    return crypto_market_heatmap_to_png(
        df,
        output_path,
        title=title,
        max_abs_change=max_abs_change,
        top_n=50 if top_n is None else top_n,
        figsize=figsize,
        dpi=dpi,
        area_groups=area_groups,
    )


def _prepare_heatmap_plot_df(
    df: pd.DataFrame,
    *,
    top_n: int | None = None,
    area_groups: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, str]:
    area_col = "market_cap" if "market_cap" in df.columns else "quote_volume"
    required_cols = ["base_asset", "last_price", "price_change_percent", area_col]
    ensure_required_columns(df, required_cols=required_cols, context="heatmap")

    plot_df = df.loc[:, required_cols].dropna(subset=[area_col]).copy()
    plot_df = plot_df[plot_df[area_col] > 0]
    if plot_df.empty:
        raise ValueError("Heatmap data is empty.")

    plot_df = plot_df.sort_values(by=area_col, ascending=False).reset_index(drop=True)
    if top_n is not None:
        plot_df = plot_df.head(top_n).reset_index(drop=True)
    plot_df["weighted_area"] = _apply_treemap_area_groups(
        plot_df,
        area_col=area_col,
        area_groups=area_groups,
    )
    return plot_df, area_col


def _crypto_market_treemap_to_png_echarts(
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
    if (
        opts is None
        or TreeMap is None
        or JsCode is None
        or CurrentConfig is None
        or make_snapshot is None
        or snapshot is None
    ):
        raise RuntimeError("pyecharts snapshot dependencies are not available.")
    if not ECHARTS_JS.exists():
        raise FileNotFoundError(
            f"Missing local ECharts asset at {ECHARTS_JS}. "
            "Download echarts.min.js to data/pyecharts_assets first."
        )

    out_path = prepare_output_path(output_path)
    plot_df, area_col = _prepare_heatmap_plot_df(
        df,
        top_n=top_n,
        area_groups=area_groups,
    )
    items = _pyecharts_treemap_items(
        plot_df,
        area_col=area_col,
        max_abs_change=max_abs_change,
    )

    width_px = max(1600, int(figsize[0] * 120))
    height_px = max(900, int(figsize[1] * 120))
    CurrentConfig.ONLINE_HOST = PYECHARTS_ASSET_DIR.resolve().as_uri() + "/"

    chart = TreeMap(
        init_opts=opts.InitOpts(
            width=f"{width_px}px",
            height=f"{height_px}px",
            bg_color="#ffffff",
            renderer="canvas",
        )
    )
    chart.add(
        series_name=title or "Crypto Heatmap",
        data=items,
        width="100%",
        height="100%",
        roam=False,
        node_click=False,
        visible_min=1,
        leaf_depth=1,
        label_opts=opts.LabelOpts(
            is_show=True,
            position="inside",
            formatter=JsCode(
                """
                function(params) {
                    return params.data.label_text || params.name;
                }
                """
            ),
            color="#ffffff",
            font_size=18,
            font_family="Arial",
            font_weight="bold",
            overflow="break",
        ),
        upper_label_opts=opts.LabelOpts(is_show=False),
        itemstyle_opts=opts.TreeMapItemStyleOpts(
            border_color="#3f6138",
            border_width=1,
            gap_width=1,
        ),
        breadcrumb_opts=opts.TreeMapBreadcrumbOpts(is_show=False),
        tooltip_opts=opts.TooltipOpts(
            formatter=JsCode(
                """
                function(params) {
                    const data = params.data || {};
                    const price = data.price_display || '';
                    const change = data.change_display || '';
                    const area = data.area_display || '';
                    return [params.name, price, change, area].filter(Boolean).join('<br/>');
                }
                """
            )
        ),
    )
    chart.set_global_opts(
        title_opts=opts.TitleOpts(title=title),
        legend_opts=opts.LegendOpts(is_show=False),
    )
    html_path = out_path.with_suffix(".html")
    make_snapshot(
        snapshot,
        chart.render(str(html_path)),
        str(out_path),
        delay=2,
        pixel_ratio=max(2, int(round(dpi / 120))),
    )
    if html_path.exists():
        html_path.unlink()
    return out_path


def _pyecharts_treemap_items(
    plot_df: pd.DataFrame,
    *,
    area_col: str,
    max_abs_change: float,
) -> list[dict[str, object]]:
    total_weight = float(plot_df["weighted_area"].sum())
    items: list[dict[str, object]] = []
    for row in plot_df.itertuples(index=False):
        weight = 0.0 if total_weight <= 0 else float(row.weighted_area) / total_weight
        label_text = _pyecharts_heatmap_label(
            base_asset=str(row.base_asset),
            price=None if pd.isna(row.last_price) else float(row.last_price),
            change=(
                None
                if pd.isna(row.price_change_percent)
                else float(row.price_change_percent)
            ),
            weight=weight,
        )
        price_display = (
            ""
            if pd.isna(row.last_price)
            else format_heatmap_price(float(row.last_price))
        )
        change_display = (
            ""
            if pd.isna(row.price_change_percent)
            else f"{float(row.price_change_percent):+.2f}%"
        )
        items.append(
            {
                "name": str(row.base_asset),
                "value": max(float(row.weighted_area) * 10_000, 1),
                "label_text": label_text,
                "price_display": price_display,
                "change_display": change_display,
                "area_display": f"{area_col}: {float(getattr(row, area_col)):,.0f}",
                "itemStyle": {
                    "color": _rgb_tuple_to_hex(
                        market_change_color(
                            None
                            if pd.isna(row.price_change_percent)
                            else float(row.price_change_percent),
                            max_abs_change,
                        )
                    )
                },
            }
        )
    return items


def _pyecharts_heatmap_label(
    *,
    base_asset: str,
    price: float | None,
    change: float | None,
    weight: float,
) -> str:
    change_text = "-" if change is None or pd.isna(change) else f"{float(change):+.2f}%"
    price_text = (
        "" if price is None or pd.isna(price) else format_heatmap_price(float(price))
    )
    if weight >= 0.045:
        return f"{base_asset}\n{price_text}\n{change_text}"
    return f"{base_asset}\n{change_text}"


def _rgb_tuple_to_hex(rgb: tuple[float, float, float]) -> str:
    channels = [max(0, min(255, int(round(channel * 255)))) for channel in rgb]
    return "#{:02x}{:02x}{:02x}".format(*channels)


def _crypto_market_treemap_to_png_matplotlib(
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
    out_path = prepare_output_path(output_path)
    plot_df, area_col = _prepare_heatmap_plot_df(
        df,
        top_n=top_n,
        area_groups=area_groups,
    )
    resolved_area_groups = area_groups or {
        "BTC": 0.25,
        "ETH,BNB,XRP,SOL": 0.2,
    }
    rects = _grouped_treemap_rects(
        plot_df,
        area_col="weighted_area",
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
        color = market_change_color(change, max_abs_change)
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

    return save_figure(fig, out_path, dpi=dpi)
