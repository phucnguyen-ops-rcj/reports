from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.clients.exchanges.kucoin import KucoinClient


def test_fetch_history_spot_filters_candles_before_trading_start_day():
    client = KucoinClient(
        spot_base_url="https://spot.test",
        futures_base_url="https://futures.test",
    )

    def fake_get(
        base_url: str, endpoint: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        assert base_url == "https://spot.test"
        if endpoint == "/api/v1/market/candles":
            return {
                "code": "200000",
                "data": [
                    ["1781568000", "3.7", "2.4", "3.7", "2.4", "100", "275"],
                    ["1781481600", "6.0", "6.0", "6.0", "6.0", "0", "0"],
                    ["1781395200", "7.8", "6.0", "8.2", "6.0", "80", "532"],
                ],
            }
        if endpoint == "/api/v2/symbols/BEAT-USDT":
            return {
                "code": "200000",
                "data": {
                    "symbol": "BEAT-USDT",
                    "tradingStartTime": 1781596800000,
                },
            }
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    client._get = fake_get  # type: ignore[method-assign]

    rows = client._fetch_history_spot(
        "BEAT-USDT",
        "BEAT",
        datetime(2026, 6, 14, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )

    assert [row["date"].date().isoformat() for row in rows] == ["2026-06-16"]
    assert [row["usd_volume_24h"] for row in rows] == [550.0]


def test_fetch_history_spot_keeps_all_candles_without_trading_start_time():
    client = KucoinClient(
        spot_base_url="https://spot.test",
        futures_base_url="https://futures.test",
    )

    def fake_get(
        base_url: str, endpoint: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        assert base_url == "https://spot.test"
        if endpoint == "/api/v1/market/candles":
            return {
                "code": "200000",
                "data": [
                    ["1781568000", "1", "1", "1", "1", "10", "20"],
                    ["1781481600", "1", "1", "1", "1", "10", "30"],
                ],
            }
        if endpoint == "/api/v2/symbols/BTC-USDT":
            return {"code": "200000", "data": {"tradingStartTime": None}}
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    client._get = fake_get  # type: ignore[method-assign]

    rows = client._fetch_history_spot(
        "BTC-USDT",
        "BTC",
        datetime(2026, 6, 15, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )

    assert [row["date"].date().isoformat() for row in rows] == [
        "2026-06-16",
        "2026-06-15",
    ]
    assert [row["usd_volume_24h"] for row in rows] == [40.0, 60.0]
