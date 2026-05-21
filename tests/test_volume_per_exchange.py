from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.scripts.alt_bb_ata.volume_per_exchange import (
    build_exchange_volume_chart,
    _normalize_volume_history,
)


class FakeInfluxDBClient:
    def get_trade_amount_history(
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
                    pd.Timestamp("2026-05-09"),
                ],
                "measurement": ["m1", "m1"],
                "our_amount": [120.0, 240.0],
            }
        )


def test_normalize_volume_history() -> None:
    df = _normalize_volume_history(
        pd.DataFrame(
            {
                "date": [
                    pd.Timestamp("2026-05-08"),
                    pd.Timestamp("2026-05-09"),
                ],
                "measurement": ["m1", "m1"],
                "our_amount": [120.0, 240.0],
            }
        ),
        report_date="2026-05-09",
        days=2,
    )

    assert list(df["volume"]) == [120.0, 240.0]


def test_build_exchange_volume_chart(tmp_path: Path) -> None:
    chart = build_exchange_volume_chart(
        {
            "page_no": 2,
            "page_count": 6,
            "label": "Binance ALTUSDT",
            "trade_measurements": ["binance_binancecpp_ALT_USDT_1_trade"],
            "filename": "binance_altusdt_volume.png",
        },
        report_date="2026-05-10",
        days=2,
        output_dir=tmp_path,
        influxdb_client=FakeInfluxDBClient(),
    )

    assert chart.available is True
    assert chart.output_path.exists()
