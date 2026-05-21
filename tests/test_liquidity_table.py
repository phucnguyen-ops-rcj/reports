from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.scripts.alt_bb_ata.liquidity_table import (
    build_liquidity_table_chart,
    load_liquidity_table_data,
)
from src.scripts.alt_bb_ata.liquidity_public_data import (
    calculate_depth_totals,
    calculate_period_market_share,
)


class FakeInfluxDBClient:
    def __init__(self, totals: dict[tuple[str, ...], float]) -> None:
        self.totals = totals

    def get_trade_notional_history(
        self,
        measurement_names: list[str],
        *,
        bucket: str = "Prod",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        _ = bucket
        _ = days
        _ = report_date
        _ = timezone
        total = self.totals.get(tuple(measurement_names), 0.0)
        if total == 0:
            return pd.DataFrame(columns=["date", "measurement", "our_notional"])
        return pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-05-20")],
                "measurement": [measurement_names[0]],
                "our_notional": [total],
            }
        )


class FakePublicClient:
    def __init__(self, quote_volume_24h: float) -> None:
        self.quote_volume_24h = quote_volume_24h

    def get_spot_order_book(self, symbol: str) -> dict[str, object]:
        _ = symbol
        return {
            "bids": [(100.0, 10.0), (99.0, 5.0), (95.0, 1.0)],
            "asks": [(101.0, 10.0), (102.0, 5.0), (106.0, 1.0)],
        }

    def get_spot_quote_volume_history(
        self,
        symbol: str,
        *,
        days: int,
        report_date: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        _ = symbol
        _ = report_date
        return pd.DataFrame(
            {
                "date": pd.date_range("2026-05-07", periods=days, freq="D"),
                "quote_volume": [self.quote_volume_24h] * days,
            }
        )


def test_calculate_depth_totals() -> None:
    plus_depth, minus_depth = calculate_depth_totals(
        {
            "bids": [(100.0, 10.0), (99.0, 5.0), (95.0, 1.0)],
            "asks": [(101.0, 10.0), (102.0, 5.0), (106.0, 1.0)],
        }
    )

    assert plus_depth == 1010.0 + 510.0
    assert minus_depth == 1000.0 + 495.0


def test_calculate_period_market_share() -> None:
    share = calculate_period_market_share(
        pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-05-07"), pd.Timestamp("2026-05-08")],
                "measurement": ["a", "a"],
                "our_notional": [100.0, 300.0],
            }
        ),
        pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-05-07"), pd.Timestamp("2026-05-08")],
                "quote_volume": [1000.0, 3000.0],
            }
        ),
    )
    assert share == 0.1


def test_load_liquidity_table_data() -> None:
    df = load_liquidity_table_data(
        "ALT",
        days=14,
        influxdb_client=FakeInfluxDBClient(
            {
                ("binance_binancecpp_ALT_USDC_trade",): 1400.0,
                ("kucoin_kucoincpp_KALT_USDT_wo_vol_trade",): 280.0,
            }
        ),
        public_clients={
            "binance": FakePublicClient(1000.0),
            "kucoin": FakePublicClient(700.0),
        },
        row_configs=[
            {
                "exchange": "binance",
                "exchange_label": "Binance",
                "pair": "ALTUSDC",
                "public_symbol": "ALTUSDC",
                "trade_measurements": ["binance_binancecpp_ALT_USDC_trade"],
                "spread_bps": 30,
            },
            {
                "exchange": "kucoin",
                "exchange_label": "Kucoin",
                "pair": "ALTUSDT",
                "public_symbol": "KALT-USDT",
                "trade_measurements": ["kucoin_kucoincpp_KALT_USDT_wo_vol_trade"],
                "spread_bps": 20,
            },
        ],
    )

    assert list(df["exchange"]) == ["Binance", "Kucoin"]
    assert df.loc[0, "weekly_average_market_share"] == pytest.approx(0.1)
    assert df.loc[1, "weekly_average_market_share"] == pytest.approx(
        280.0 / (700.0 * 14)
    )
    assert df.loc[0, "market_plus_depth"] == 1520.0
    assert df.loc[0, "market_minus_depth"] == 1495.0


def test_build_liquidity_table_renders_png(tmp_path: Path) -> None:
    chart = build_liquidity_table_chart(
        "ALT",
        days=14,
        output_dir=tmp_path,
        influxdb_client=FakeInfluxDBClient(
            {("binance_binancecpp_ALT_USDC_trade",): 1400.0}
        ),
        public_clients={
            "binance": FakePublicClient(1000.0),
            "bybit": FakePublicClient(1000.0),
            "gateio": FakePublicClient(1000.0),
            "kucoin": FakePublicClient(1000.0),
        },
    )

    assert chart.output_path.exists()
