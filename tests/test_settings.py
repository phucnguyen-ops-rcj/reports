from __future__ import annotations

from pathlib import Path

from src.settings import Settings


def test_secrets_load_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("REDISCLI_AUTH", raising=False)
    monkeypatch.delenv("RCJ_OPS_BEARER_TOKEN", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "REDISCLI_AUTH=redis-from-dotenv\n" "RCJ_OPS_BEARER_TOKEN=ops-from-dotenv\n",
        encoding="utf-8",
    )

    settings = Settings(
        _env_file=env_file,
        signal_base_url="http://signal.test",
        signal_sender="+10000000000",
        signal_group_id="group.test",
        coingecko_base_url="https://coingecko.test",
        coingecko_api_key="coingecko-key",
        influxdb_base_url="http://influxdb.test",
        influxdb_token="influxdb-token",
        influxdb_org="test-org",
        kucoin_spot_base_url="https://kucoin-spot.test",
        kucoin_future_base_url="https://kucoin-futures.test",
    )

    assert settings.redis_password == "redis-from-dotenv"
    assert settings.rcj_ops_bearer_token == "ops-from-dotenv"
