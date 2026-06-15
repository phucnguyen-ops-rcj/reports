from __future__ import annotations

import pandas as pd

from src.clients.third_parties.coinmarketcap import CoinMarketCapClient
from src.scripts.alt_bb_ata.perp_market_analysis import (
    build_liquidation_sentence,
)


class FakeCoinMarketCapClient(CoinMarketCapClient):
    def _load_liquidation_chart_payload(
        self,
        *,
        symbol: str | None,
        exchange: str | None,
    ) -> dict[str, object]:
        _ = symbol
        _ = exchange
        return {
            "selected_coin_name": "Altlayer",
            "selected_coin_symbol": "ALT",
            "selected_exchange": "all",
            "series": [
                {
                    "name": "Long",
                    "data": [
                        {"x": 1781308800000, "y": 100.0},
                        {"x": 1781395200000, "y": 300.0},
                    ],
                },
                {
                    "name": "Short",
                    "data": [
                        {"x": 1781308800000, "y": -100.0},
                        {"x": 1781395200000, "y": -200.0},
                    ],
                },
            ],
        }


def test_coinmarketcap_liquidation_dates_use_report_day_boundary() -> None:
    df = FakeCoinMarketCapClient().get_liquidation_chart(symbol="ALT")

    assert list(df["date"]) == [
        pd.Timestamp("2026-06-14", tz="UTC"),
        pd.Timestamp("2026-06-15", tz="UTC"),
    ]


def test_build_liquidation_sentence_matches_report_date() -> None:
    df = FakeCoinMarketCapClient().get_liquidation_chart(symbol="ALT")

    assert build_liquidation_sentence(df, report_date="2026-06-15") == (
        "Perp liquidations increased over the past 24H at "
        "~$300 longs and ~$200 shorts liquidated as on 15 June."
    )
