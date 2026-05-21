from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.scripts.alt_bb_ata.aggregate_buy_sell_volume import (
    build_aggregate_buy_sell_volume_chart,
    _normalize_buy_sell_history,
)


class FakeInfluxDBClient:
    def get_trade_buy_sell_notional_history(
        self,
        measurement_names: list[str],
        *,
        bucket: str = "Prod",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        _ = measurement_names
        _ = bucket
        _ = days
        _ = report_date
        _ = timezone
        return pd.DataFrame(
            {
                "date": [
                    pd.Timestamp("2026-05-08"),
                    pd.Timestamp("2026-05-08"),
                    pd.Timestamp("2026-05-09"),
                ],
                "side": ["buy", "sell", "buy"],
                "notional": [100.0, 80.0, 40.0],
            }
        )


class FakeBinanceClient:
    class _Kline:
        def __init__(
            self,
            open_time_ms: int,
            open_price: float,
            high_price: float,
            low_price: float,
            close_price: float,
            volume: float,
        ) -> None:
            self.open_time_ms = open_time_ms
            self.open_price = open_price
            self.high_price = high_price
            self.low_price = low_price
            self.close_price = close_price
            self.volume = volume

    def get_klines(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        limit: int = 30,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[_Kline]:
        _ = symbol
        _ = interval
        _ = limit
        _ = start_time_ms
        _ = end_time_ms
        return [
            self._Kline(1778198400000, 1.0, 1.1, 0.9, 1.05, 10.0),
            self._Kline(1778284800000, 1.05, 1.2, 1.0, 1.15, 11.0),
        ]


def test_normalize_buy_sell_history() -> None:
    df = _normalize_buy_sell_history(
        pd.DataFrame(
            {
                "date": [
                    pd.Timestamp("2026-05-08"),
                    pd.Timestamp("2026-05-08"),
                    pd.Timestamp("2026-05-09"),
                ],
                "side": ["buy", "sell", "buy"],
                "notional": [100.0, 80.0, 40.0],
            }
        ),
        report_date="2026-05-09",
        days=2,
    )

    assert list(df["buy"]) == [100.0, 40.0]
    assert list(df["sell"]) == [80.0, 0.0]


def test_build_aggregate_buy_sell_volume_chart(tmp_path: Path) -> None:
    chart = build_aggregate_buy_sell_volume_chart(
        "ALT",
        report_date="2026-05-09",
        days=2,
        output_dir=tmp_path,
        influxdb_client=FakeInfluxDBClient(),
        binance_client=FakeBinanceClient(),
    )

    assert chart.output_path.exists()
