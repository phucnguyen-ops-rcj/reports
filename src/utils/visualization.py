"""Utility functions for converting DataFrames to visualization formats."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


def dataframe_to_png(df: pd.DataFrame, output_path: str | Path, title: str = "", figsize: tuple = (12, 6)) -> Path:
    """Convert DataFrame to PNG image using matplotlib.
    
    Args:
        df: DataFrame to convert
        output_path: Path to save PNG file
        title: Optional title for the image
        figsize: Figure size as (width, height) in inches
        
    Returns:
        Path to saved PNG file
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=figsize)
    ax.axis('tight')
    ax.axis('off')
    
    # Create table
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='left', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    
    # Style header
    for i in range(len(df.columns)):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Alternate row colors
    for i in range(1, len(df) + 1):
        for j in range(len(df.columns)):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#f0f0f0')
            else:
                table[(i, j)].set_facecolor('#ffffff')
    
    if title:
        plt.title(title, fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    
    return out_path


def dataframe_to_png_styled(df: pd.DataFrame, output_path: str | Path, title: str = "", 
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
    
    # Format numeric values to 2 decimal places
    df_display = df.copy()
    for col in df_display.columns:
        if pd.api.types.is_numeric_dtype(df_display[col]):
            df_display[col] = df_display[col].apply(
                lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and np.isfinite(x) else x
            )
    
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
