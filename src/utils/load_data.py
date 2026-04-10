import pandas as pd
import logging
import time
from src.utils.wrangle import wrangle_data

logger = logging.getLogger(__name__)


def load_local_data(file_path):
    # use logging and time to show how long it takes to load the data
    start_time = time.time()
    logger.info(f"Loading data from {file_path}...")
    df = pd.read_csv(file_path)
    df = wrangle_data(df)
    end_time = time.time()
    logger.info(f"{len(df)} rows loaded in {end_time - start_time:.2f} seconds.")
    return df


def load_api_data():
    pass


if __name__ == "__main__":
    from src.settings import get_settings
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format='%(asctime)s - %(levelname)s - %(message)s')
    df = load_local_data(settings.csv_input_path)
    print(df.head())