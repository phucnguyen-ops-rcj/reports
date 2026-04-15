from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # data source
    source: str = Field(default="local", description="Data source: 'local' or 'api'")  # can be "local" or "api"

    # Signal messaging
    signal_base_url: str
    signal_sender: str
    signal_recipient: str | None = Field(default=None)
    signal_group_id: str

    # CoinGecko API
    coingecko_base_url: str
    coingecko_api_key: str = Field(default_factory=lambda: os.environ["COINGECKO_API_KEY"])

    # influxDB
    influxdb_base_url: str
    influxdb_token: str = Field(default_factory=lambda: os.environ["INFLUXDB_TOKEN"])
    influxdb_org: str

    # KuCoin API
    kucoin_spot_base_url: str
    kucoin_future_base_url: str
    
    # File paths
    net_pnl_input_path: str = Field(default="data/trades.csv")
    trading_volume_input_path: str = Field(default="data/trading_volume.csv")
    input_dir: str = Field(default="data")
    output_dir: str = Field(default="results")

    # Logging
    log_level: str = Field(default="INFO")

    # Timezone
    tz: str = Field(default="Asia/Singapore")

    # Optional features
    enable_signal_notifications: bool = Field(default=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
# print(settings)
