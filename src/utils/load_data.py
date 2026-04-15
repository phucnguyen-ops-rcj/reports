import pandas as pd
import logging
import time
from pathlib import Path
from src.settings import get_settings
from src.utils.save_data import save_csv
from src.utils.wrangle import wrangle_pnl_data, wrangle_trading_volume_data
from typing import Literal
from src.clients.kucoin import KucoinClient
from src.utils.constants import MONITORING_SYMBOLS
from datetime import datetime
logger = logging.getLogger(__name__)


def load_pnl_data(source: Literal["local", "api"] = "local", file_path = None):
    # use logging and time to show how long it takes to load the data
    start_time = time.time()
    if source == "local":
        logger.info(f"Loading data from {file_path}...")
        df = pd.read_csv(file_path)
    else:
        logger.info(f"Loading data from API...")
    df = wrangle_pnl_data(df)
    end_time = time.time()
    logger.info(f"{len(df)} rows loaded in {end_time - start_time:.2f} seconds.")
    return df


def load_trading_volume_data(source: Literal["local", "api"] = "local", file_path = None):
    start_time = time.time()
    if source == "local":
        # TODO: move this to else block when influxdb is implemented for net_pnl
        logger.info(f"Loading trading volume data from {file_path}...")
        # df = pd.read_csv(file_path)
        kucoin_client = KucoinClient()
        df = kucoin_client.get_history_volume(MONITORING_SYMBOLS, 100)
        app_settings = get_settings()
        out_dir = Path(app_settings.input_dir) / "trading_volume"
        save_csv(df, out_dir, f"")
    else:
        logger.info(f"Loading trading volume data from API...")
    df = wrangle_trading_volume_data(df)
    end_time = time.time()
    logger.info(f"{len(df)} rows loaded in {end_time - start_time:.2f} seconds.")
    return df


if __name__ == "__main__":
    from src.settings import get_settings
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format='%(asctime)s - %(levelname)s - %(message)s')
    df = load_trading_volume_data("data/kucoin_24h_volume_summary_2026-04-13_04-48-18.csv")
    print(df.head())