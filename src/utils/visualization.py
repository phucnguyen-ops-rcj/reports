"""Utility functions for converting DataFrames to visualization formats."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


def _format_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Format numeric columns with comma separators (e.g. 1000000 → 1,000,000.00)."""
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and df[col].dtype != bool:
            df[col] = df[col].apply(
                lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) and np.isfinite(x) else x
            )
    return df


def net_pnl_to_png_styled(df: pd.DataFrame, output_path: str | Path, title: str = "", 
                           highlight_col: str | None = None, cmap: str = "RdYlGn") -> Path:
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
    ax.axis('tight')
    ax.axis('off')
    
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
    
    table = ax.table(cellText=df_display.values, colLabels=df_display.columns, cellLoc='left', loc='center',
                    cellColours=color_array)
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)
    
    # Style header
    for i in range(len(df_display.columns)):
        table[(0, i)].set_facecolor('#2c3e50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    if title:
        plt.title(title, fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    
    return out_path


def trading_volume_to_png_styled(df: pd.DataFrame, output_path: str | Path, title: str = "") -> Path:
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
    ax.axis('tight')
    ax.axis('off')

    # Prepare cell colors — white by default, light red for rows that miss the requirement
    color_array = np.ones((len(df_display), len(df_display.columns), 3))
    if "meets_requirement" in df_display.columns:
        for i, meets in enumerate(df_display["meets_requirement"]):
            if not meets:
                color_array[i, :] = [1.0, 0.85, 0.85]  # light red for failing rows

    table = ax.table(
        cellText=df_display.values,
        colLabels=df_display.columns,
        cellLoc='left',
        loc='center',
        cellColours=color_array,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)

    # Style header
    for i in range(len(df_display.columns)):
        table[(0, i)].set_facecolor('#2c3e50')
        table[(0, i)].set_text_props(weight='bold', color='white')

    if title:
        plt.title(title, fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig(out_path, dpi=100, bbox_inches='tight')
    plt.close(fig)

    return out_path