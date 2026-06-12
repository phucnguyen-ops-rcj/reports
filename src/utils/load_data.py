import pandas as pd
import logging
import time
from pathlib import Path
from typing import List
from src.settings import app_settings
from src.utils.save_data import save_csv
from src.utils.wrangle import wrangle_pnl_data, wrangle_trading_volume_data
from typing import Literal
from src.clients.exchanges.kucoin import KucoinClient
from src.utils.constants import MONITORING_SYMBOLS
from src.utils.net_pnl_analysis_data import build_analysis_dataframe

logger = logging.getLogger(__name__)


def load_pnl_data(
    source: Literal["local", "api"] = "local", file_path: Path | str | None = None
):
    start_time = time.time()
    if source == "local":
        if file_path is None:
            raise ValueError("file_path is required when source is 'local'")
        logger.info(f"Loading data from {file_path}...")
        df = pd.read_csv(file_path)
    else:
        logger.info("Loading data from API...")
        df = build_analysis_dataframe()
        out_dir = Path(app_settings.input_dir) / "net_pnl"
        save_csv(df, out_dir, "")
    df = wrangle_pnl_data(df)
    # df = df[df["mapped_symbol"].isin(MONITORING_SYMBOLS)].reset_index(drop=True)
    end_time = time.time()
    logger.info(f"{len(df)} rows loaded in {end_time - start_time:.2f} seconds.")
    return df


def load_trading_volume_data(
    source: Literal["local", "api"] = "local",
    file_path=None,
    symbols: List[str] = MONITORING_SYMBOLS,
):
    start_time = time.time()
    if source == "local":
        if file_path is None:
            raise ValueError("file_path is required when source is 'local'")
        logger.info(f"Loading trading volume data from {file_path}...")
        df = pd.read_csv(file_path)
    else:
        logger.info("Loading trading volume data from API...")
        kucoin_client = KucoinClient()
        df = kucoin_client.get_history_volume(symbols, 100)
        out_dir = Path(app_settings.input_dir) / "trading_volume"
        save_csv(df, out_dir, "")
    df = wrangle_trading_volume_data(df)
    end_time = time.time()
    logger.info(f"{len(df)} rows loaded in {end_time - start_time:.2f} seconds.")
    return df


if __name__ == "__main__":
    logging.basicConfig(
        level=app_settings.log_level.upper(),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    pnl_df = load_pnl_data("api")
    print(pnl_df.head())
