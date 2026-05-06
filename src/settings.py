from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    source: Literal["local", "api"] = Field(
        default="local", description="Data source: 'local' or 'api'"
    )

    # Signal messaging
    signal_base_url: str
    signal_sender: str
    signal_recipient: str | None = Field(default=None)
    signal_group_id: str

    # CoinGecko API
    coingecko_base_url: str
    coingecko_api_key: str = Field(
        default_factory=lambda: os.environ["COINGECKO_API_KEY"]
    )

    # influxDB
    influxdb_base_url: str
    influxdb_token: str = Field(default_factory=lambda: os.environ["INFLUXDB_TOKEN"])
    influxdb_org: str

    # KuCoin API
    kucoin_spot_base_url: str
    kucoin_future_base_url: str

    # ALT report third-party sources
    binance_base_url: str = Field(default="https://api.binance.com")
    binance_futures_base_url: str = Field(default="https://fapi.binance.com")
    bybit_base_url: str = Field(default="https://api.bybit.com")
    coinank_base_url: str = Field(default="https://coinank.com")
    coinank_api_base_url: str = Field(default="https://api.coinank.com")
    coinmarketcap_base_url: str = Field(default="https://pro-api.coinmarketcap.com")
    coinmarketcap_api_key: str = Field(
        default_factory=lambda: os.environ.get("COINMARKETCAP_API_KEY", "")
    )
    coinshares_base_url: str = Field(default="https://researchblog.coinshares.com")
    farside_base_url: str = Field(default="https://farside.co.uk")
    tradingdigits_base_url: str = Field(default="https://www.tradingdigits.io")
    tradingview_base_url: str = Field(default="https://www.tradingview.com")

    # RCJ ops API
    rcj_ops_bearer_token: str = Field(
        default_factory=lambda: os.environ.get("RCJ_OPS_BEARER_TOKEN", "")
    )

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


app_settings = get_settings()
# print(app_settings)
