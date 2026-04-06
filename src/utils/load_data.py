import pandas as pd
import logging
import time
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from src.utils.wrangle import wrangle_data


def load_local_data(file_path):
    # use logging and time to show how long it takes to load the data
    start_time = time.time()
    logging.info(f"Loading data from {file_path}...")
    df = pd.read_csv(file_path)
    df = wrangle_data(df)
    end_time = time.time()
    logging.info(f"{len(df)} rows loaded in {end_time - start_time:.2f} seconds.")
    return df


def load_api_data():
    pass


if __name__ == "__main__":
    file_path = "data/analysis_data.csv"
    df = load_local_data(file_path)
    print(df.head())