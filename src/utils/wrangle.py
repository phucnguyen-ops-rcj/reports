from .constants import SYMBOL_MAPPING, ANALYSIS_DATA_COLUMNS
from .dataframe import (
    extract_prefix_column,
    map_column_with_fallback,
)


def wrangle_data(df):
    # remove nan rows
    df = df.dropna(axis=0).reset_index(drop=True)
    # standardize column names
    df.columns = ANALYSIS_DATA_COLUMNS  # NOTE: the order of columns in the raw data must match the order in ANALYSIS_DATA_COLUMNS
    # standardize strategy names
    df["strategy"] = (
      df["strategy"]
      .str.replace(" ", "", regex=True)
      .str.lower()
    )

    # symbols of the same tokens will have same name, e.g. BONK and 1000BONK will both be mapped to BONK
    df = map_column_with_fallback(df, "symbol", "mapped_symbol", SYMBOL_MAPPING)

    # standardize strategy names by taking the first part before any hyphen
    df = extract_prefix_column(df, "strategy", "base_strategy")

    # convert str type to float: npnl_r+un and npnl/volume_%
    df["npnl_r+un"] = df["npnl_r+un"].astype(float)
    df["npnl/volume_%"] = df["npnl/volume_%"].str.rstrip("%").astype(float) / 100
    return df
