from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def required_env(name: str) -> str:
    return os.environ[name]


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
    signal_base_url: str = Field(
        default_factory=lambda: required_env("SIGNAL_BASE_URL")
    )
    signal_sender: str = Field(default_factory=lambda: required_env("SIGNAL_SENDER"))
    signal_recipient: str | None = Field(default=None)
    signal_group_id: str = Field(
        default_factory=lambda: required_env("SIGNAL_GROUP_ID")
    )

    # CoinGecko API
    coingecko_base_url: str = Field(
        default_factory=lambda: required_env("COINGECKO_BASE_URL")
    )
    coingecko_api_key: str = Field(
        default_factory=lambda: os.environ["COINGECKO_API_KEY"]
    )

    # influxDB
    influxdb_base_url: str = Field(
        default_factory=lambda: required_env("INFLUXDB_BASE_URL")
    )
    influxdb_token: str = Field(default_factory=lambda: os.environ["INFLUXDB_TOKEN"])
    influxdb_org: str = Field(default_factory=lambda: required_env("INFLUXDB_ORG"))

    # Redis
    redis_host: str = Field(default="172.31.33.22")
    redis_port: int = Field(default=6380)
    redis_username: str = Field(default="newuser1")
    redis_password: str = Field(default_factory=lambda: os.environ["REDISCLI_AUTH"])
    redis_db: int = Field(default=0)

    # KuCoin API
    kucoin_spot_base_url: str = Field(
        default_factory=lambda: required_env("KUCOIN_SPOT_BASE_URL")
    )
    kucoin_future_base_url: str = Field(
        default_factory=lambda: required_env("KUCOIN_FUTURE_BASE_URL")
    )

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
    rcj_trading_base_url: str = Field(default="https://1rf9t4k2tc.xyz")

    # RCJ ops API
    rcj_ops_bearer_token: str = Field(
        default_factory=lambda: os.environ.get("RCJ_OPS_BEARER_TOKEN", "")
    )
    rcj_ops_base_endpoint: str = Field(default="http://18.176.93.228")
    rcj_ops_timeout_seconds: int = Field(default=60)
    rcj_ops_execution_mode: Literal["ssh", "local"] = Field(default="ssh")
    rcj_ops_ssh_host: str = Field(default="T1_newuser1")

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
