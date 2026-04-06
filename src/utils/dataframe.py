from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd


def map_column_with_fallback(
    df: pd.DataFrame,
    source_col: str,
    target_col: str,
    mapping: Mapping[str, str],
) -> pd.DataFrame:
    result = df.copy()
    result[target_col] = result[source_col].map(mapping).fillna(result[source_col])
    return result


def extract_prefix_column(
    df: pd.DataFrame,
    source_col: str,
    target_col: str,
    separator: str = "-",
) -> pd.DataFrame:
    result = df.copy()
    result[target_col] = result[source_col].str.split(separator).str[0].astype("string")
    return result


def calculate_ratio_column(
    df: pd.DataFrame,
    numerator_col: str,
    denominator_col: str,
    target_col: str,
    scale: float = 1.0,
) -> pd.DataFrame:
    result = df.copy()
    result[target_col] = result[numerator_col] / result[denominator_col] * scale
    return result


def aggregate_metric_columns(
    df: pd.DataFrame,
    group_by_cols: Sequence[str],
    metric_cols: Sequence[str],
) -> pd.DataFrame:
    return df.groupby(list(group_by_cols))[list(metric_cols)].sum().reset_index()


def filter_rows_below_threshold(
    df: pd.DataFrame,
    value_col: str,
    threshold: float,
) -> pd.DataFrame:
    return df[df[value_col] < threshold].copy()
