"""Shared helpers for visualization renderers."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]
PYECHARTS_ASSET_DIR = REPO_ROOT / "data" / "pyecharts_assets"
ECHARTS_JS = PYECHARTS_ASSET_DIR / "echarts.min.js"


def prepare_output_path(output_path: str | Path) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path


def ensure_required_columns(
    df: pd.DataFrame,
    *,
    required_cols: list[str],
    context: str,
) -> None:
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing {context} columns: {', '.join(missing_cols)}")


def prepare_time_series_plot_df(
    df: pd.DataFrame,
    *,
    required_cols: list[str],
    dropna_subset: list[str],
    days: int,
    column_context: str,
    empty_message: str,
    normalize_dates_utc: bool = False,
) -> pd.DataFrame:
    ensure_required_columns(df, required_cols=required_cols, context=column_context)
    plot_df = df.loc[:, required_cols].dropna(subset=dropna_subset).copy()
    if normalize_dates_utc and "date" in plot_df.columns:
        plot_df["date"] = pd.to_datetime(plot_df["date"], utc=True)
    plot_df = plot_df.sort_values(by="date").tail(days).reset_index(drop=True)
    if plot_df.empty:
        raise ValueError(empty_message)
    return plot_df


def save_figure(
    fig: plt.Figure,
    output_path: str | Path,
    *,
    dpi: int,
    tight_layout_pad: float | None = None,
    tight_layout_h_pad: float | None = None,
    facecolor: str = "white",
) -> Path:
    out_path = prepare_output_path(output_path)
    if tight_layout_pad is not None:
        plt.tight_layout(pad=tight_layout_pad, h_pad=tight_layout_h_pad)
    elif tight_layout_h_pad is not None:
        plt.tight_layout(h_pad=tight_layout_h_pad)
    else:
        plt.tight_layout()
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor=facecolor)
    plt.close(fig)
    return out_path


def format_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and df[col].dtype != bool:
            df[col] = df[col].apply(
                lambda x: f"{x:,.2f}"
                if isinstance(x, (int, float)) and np.isfinite(x)
                else x
            )
    return df


def market_change_color(
    change: float | None,
    max_abs_change: float,
) -> tuple[float, float, float]:
    if change is None or pd.isna(change):
        return to_rgb("#9aa0a6")

    intensity = min(abs(float(change)) / max_abs_change, 1.0)  # pyrefly: ignore
    if change >= 0:
        low = np.array(to_rgb("#6fa35f"))
        high = np.array(to_rgb("#2e7d32"))
    else:
        low = np.array(to_rgb("#c85252"))
        high = np.array(to_rgb("#9f2f2f"))
    return tuple(low + (high - low) * intensity)


def format_heatmap_price(value: float) -> str:
    if value >= 1000:
        return f"${value:,.2f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:,.4f}"


def format_axis_millions(value: float) -> str:
    return f"{value / 1_000_000:,.0f}M"


def format_axis_billions(value: float) -> str:
    return f"${value / 1_000_000_000:.2f}B"


def format_axis_thousands(value: float) -> str:
    return f"${value / 1_000:.2f}K"


def format_axis_signed_thousands(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f"${absolute / 1_000_000:.2f}M"
    if absolute >= 1_000:
        return f"${absolute / 1_000:.2f}K"
    return f"${absolute:.0f}"


def format_turnover_value(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "***"
    absolute = abs(float(value))  # pyrefly: ignore
    if absolute >= 1_000_000:
        return f"${absolute / 1_000_000:.2f}M"
    if absolute >= 1_000:
        return f"${absolute / 1_000:.2f}K"
    return f"${absolute:.0f}"


def format_ratio_percent(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "***"
    return f"{float(value) * 100:.2f}%"  # pyrefly: ignore


def format_percent_value(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "***"
    return f"{float(value):+.2f}%"  # pyrefly: ignore


def format_price_value(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "***"
    return f"${float(value):.6f}"  # pyrefly: ignore


def ratio_fill_color(
    ratio: float | None,
    *,
    positive: bool,
) -> tuple[float, float, float]:
    if ratio is None or not np.isfinite(ratio):
        return (1.0, 1.0, 1.0)
    ratio_value = min(max(float(ratio), 0.0), 1.0)  # pyrefly: ignore
    strength = 0.18 + 0.42 * ratio_value
    if positive:
        return (
            1.0 - 0.38 * strength,
            1.0 - 0.08 * strength,
            1.0 - 0.28 * strength,
        )
    return (
        1.0 - 0.06 * strength,
        1.0 - 0.34 * strength,
        1.0 - 0.32 * strength,
    )


def pad_axis(ax: plt.Axes, values: pd.Series) -> None:
    finite_values = values[np.isfinite(values)]
    if finite_values.empty:
        return
    max_value = float(finite_values.max())
    min_value = min(float(finite_values.min()), 0.0)
    pad = max((max_value - min_value) * 0.18, max_value * 0.05, 1.0)
    ax.set_ylim(min_value, max_value + pad)
