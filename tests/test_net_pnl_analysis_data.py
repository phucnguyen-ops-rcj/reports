from __future__ import annotations

from src.utils.net_pnl_analysis_data import (
    build_analysis_rows,
    build_market_analysis_dataframe,
    metric_delta,
)


def test_metric_delta_supports_absolute_mode():
    metric = {"first": 10, "last": 4}
    assert metric_delta(metric) == -6.0
    assert metric_delta(metric, absolute=True) == 6.0


def test_build_analysis_rows_uses_last_minus_first():
    payload = {
        "strategy1": {
            "BTC": {
                "count": {"first": 5, "last": 2},
                "tradeVolume": {"first": 1000, "last": 400},
                "netPos": {"first": 3, "last": 1},
                "netPosDol": {"first": 300, "last": 100},
                "rpnl": {"first": 10, "last": 4},
                "rpnlWFees": {"first": 8, "last": 1},
                "upnl": {"first": 6, "last": 9},
            }
        }
    }

    rows = build_analysis_rows(payload, market="spot")

    assert rows == [
        {
            "market": "spot",
            "strategy": "strategy1",
            "symbol": "BTC",
            "volume_$": 600.0,
            "net_position": -2.0,
            "net_position_$": -200.0,
            "rpnl": -6.0,
            "unpnl": 3.0,
            "rpnlwfees": -7.0,
            "npnl_r+un": -3.0,
            "npnl/volume_%": "-0.5000%",
            "trade_count": 3,
        }
    ]


def test_build_market_analysis_dataframe_for_given_symbols():
    class FakeTradingClient:
        def get_analyze(self, *, symbols, period_ms, analyze_type):
            assert symbols == ["BTC", "ETH"]
            assert period_ms == 3600
            assert str(analyze_type) == "Spot"
            return {
                "strategy1": {
                    "BTC": {
                        "count": {"first": 1, "last": 3},
                        "tradeVolume": {"first": 10, "last": 40},
                        "netPos": {"first": 2, "last": 5},
                        "netPosDol": {"first": 20, "last": 50},
                        "rpnl": {"first": 7, "last": 10},
                        "rpnlWFees": {"first": 6, "last": 9},
                        "upnl": {"first": 11, "last": 13},
                    }
                }
            }

    df = build_market_analysis_dataframe(
        market="spot",
        symbols=["BTC", "ETH"],
        period_ms=3600,
        batch_size=10,
        trading_client=FakeTradingClient(),
    )

    assert df.to_dict("records") == [
        {
            "market": "spot",
            "strategy": "strategy1",
            "symbol": "BTC",
            "volume_$": 30.0,
            "net_position": 3.0,
            "net_position_$": 30.0,
            "rpnl": 3.0,
            "unpnl": 2.0,
            "rpnlwfees": 3.0,
            "npnl_r+un": 5.0,
            "npnl/volume_%": "16.6667%",
            "trade_count": 2,
        }
    ]
