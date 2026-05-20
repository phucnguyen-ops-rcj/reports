from .constants import (
    SYMBOL_MAPPING,
    ANALYSIS_DATA_COLUMNS,
    TRADING_VOLUME_DATA_COLUMNS,
)
from .dataframe import (
    extract_prefix_column,
    map_column_with_fallback,
)


def wrangle_pnl_data(df):
    # remove nan rows
    df = df.dropna(axis=0).reset_index(drop=True)
    # standardize column names
    df.columns = ANALYSIS_DATA_COLUMNS  # NOTE: the order of columns in the raw data must match the order in ANALYSIS_DATA_COLUMNS
    # standardize strategy names
    df["strategy"] = df["strategy"].str.replace(" ", "", regex=True).str.lower()
    df["strategy"] = df["strategy"].replace(
        {
            "strategy42": "strategy4-2",
            "strategy92": "strategy9-2",
            "kucc42": "kucc4-2",
            "kucc92": "kucc9-2",
        }
    )

    # symbols of the same tokens will have same name, e.g. BONK and 1000BONK will both be mapped to BONK
    df = map_column_with_fallback(df, "symbol", "mapped_symbol", SYMBOL_MAPPING)

    # get base_strategy
    # standardize strategy names by taking the first part before any hyphen
    df = extract_prefix_column(df, "strategy", "base_strategy")
    # replace base_strategy kucc4 by strategy4
    df["base_strategy"] = df["base_strategy"].replace({"kucc4": "strategy4"})

    # convert str type to float: npnl_r+un and npnl/volume_%
    df["npnl_r+un"] = df["npnl_r+un"].astype(float)
    df["npnl/volume_%"] = df["npnl/volume_%"].str.rstrip("%").astype(float) / 100

    # round numeric columns to 2 decimal places
    df = df.round(2)
    return df


def wrangle_trading_volume_data(df):
    # standardize column names
    df.columns = TRADING_VOLUME_DATA_COLUMNS
    # df = df[df["base"].isin(MONITORING_SYMBOLS)].reset_index(drop=True)
    #     df["usd_volume_24h"] = (
    #       df["usd_volume_24h"]
    #       .str.replace(".", "", regex=False)   # remove thousands separator
    #       .str.replace(",", ".", regex=False)  # convert decimal separator
    #       .astype(float)
    #   )
    # df.to_csv("data/trading_volume/trading_volume_wrangled.csv", index=False)  # save intermediate result for debugging
    # df["usd_volume_24h"] = df["usd_volume_24h"].str.replace(",", "", regex=False).astype(float)  # strip thousands separators before converting
    # normalise timestamp: source format is "YYYY-MM-DD"
    # df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], format="%Y-%m-%d")
    return df
