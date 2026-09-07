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


class FakeCoinMarketCapPublicApiClient(CoinMarketCapClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def _get_public_json(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        self.calls.append((endpoint, params))
        if endpoint.endswith("/crypto/list"):
            return {
                "data": [
                    {
                        "id": 29073,
                        "name": "Altlayer",
                        "symbol": "ALT",
                        "slug": "altlayer",
                    }
                ]
            }
        if endpoint.endswith("/exchange/list"):
            return {"data": [{"id": 270, "name": "Binance", "slug": "binance"}]}
        return {
            "data": {
                "bars": [
                    {
                        "timestamp": "1781308800",
                        "totalLongs": "100.0",
                        "totalShorts": "40.0",
                        "coinPrice": "0.02",
                    }
                ]
            }
        }


def test_coinmarketcap_liquidation_dates_use_report_day_boundary() -> None:
    df = FakeCoinMarketCapClient().get_liquidation_chart(symbol="ALT")

    assert list(df["date"]) == [
        pd.Timestamp("2026-06-14", tz="UTC"),
        pd.Timestamp("2026-06-15", tz="UTC"),
    ]


def test_coinmarketcap_liquidation_chart_uses_public_data_api() -> None:
    client = FakeCoinMarketCapPublicApiClient()

    df = client.get_liquidation_chart(symbol="ALT", exchange="Binance")

    assert client.calls[-1] == (
        "/data-api/v3/liquidations/chart",
        {"range": "1y", "coinIds": "29073", "exchangeIds": "270"},
    )
    assert df.loc[0, "long_liquidation_usd"] == 100.0
    assert df.loc[0, "short_liquidation_usd"] == 40.0
    assert df.loc[0, "price_usd"] == 0.02
    assert df.attrs["selected_coin_symbol"] == "ALT"
    assert df.attrs["selected_exchange"] == "Binance"


def test_build_liquidation_sentence_matches_report_date() -> None:
    df = FakeCoinMarketCapClient().get_liquidation_chart(symbol="ALT")

    assert build_liquidation_sentence(df, report_date="2026-06-15") == (
        "Perp liquidations increased over the past 24H at "
        "~$300 longs and ~$200 shorts liquidated as on 15 June."
    )
