"""Generic dataframe-to-table visualization helpers."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils.visualizations.shared import (
    format_numeric_columns,
    prepare_output_path,
    save_figure,
)


def net_pnl_to_png_styled(
    df: pd.DataFrame,
    output_path: str | Path,
    title: str = "",
    highlight_col: str | None = None,
    cmap: str = "RdYlGn",
) -> Path:
    _ = highlight_col
    _ = cmap
    out_path = prepare_output_path(output_path)

    df_display = format_numeric_columns(df.copy().round(2))
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.axis("tight")
    ax.axis("off")

    color_array = np.ones((len(df_display), len(df_display.columns), 3))
    if "strategy" in df_display.columns:
        total_mask = df_display["strategy"] == "Total"
        color_array[total_mask.values, :] = [0.7, 0.9, 1.0]

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

    for i in range(len(df_display.columns)):
        table[(0, i)].set_facecolor("#2c3e50")
        table[(0, i)].set_text_props(weight="bold", color="white")

    if title:
        plt.title(title, fontsize=14, fontweight="bold", pad=20)

    return save_figure(fig, out_path, dpi=100)


def trading_volume_to_png_styled(
    df: pd.DataFrame,
    output_path: str | Path,
    title: str = "",
) -> Path:
    out_path = prepare_output_path(output_path)

    df_display = format_numeric_columns(df.copy().round(2))
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.axis("tight")
    ax.axis("off")

    color_array = np.ones((len(df_display), len(df_display.columns), 3))
    if "meets_requirement" in df_display.columns:
        for i, meets in enumerate(df_display["meets_requirement"]):
            if not meets:
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

    for i in range(len(df_display.columns)):
        table[(0, i)].set_facecolor("#2c3e50")
        table[(0, i)].set_text_props(weight="bold", color="white")

    if title:
        plt.title(title, fontsize=14, fontweight="bold", pad=20)

    return save_figure(fig, out_path, dpi=100)
