from __future__ import annotations

from src.utils.net_pnl_analysis_data import (
    build_analysis_rows,
    build_market_analysis_dataframe,
    get_symbols_by_market_with_fallback,
    load_symbols_by_market_from_input,
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


def test_load_symbols_by_market_from_input(tmp_path):
    input_path = tmp_path / "trades.csv"
    input_path.write_text(
        "Market,Symbol\n"
        "spot,ETH\n"
        "spot,BTC\n"
        "spot,ETH\n"
        "perp,SOL\n"
        "perp,BTC\n"
    )

    assert load_symbols_by_market_from_input(input_path) == {
        "spot": ["BTC", "ETH"],
        "perp": ["BTC", "SOL"],
    }


def test_get_symbols_by_market_falls_back_to_input_when_redis_fails(tmp_path):
    class FailingRedisClient:
        def get_symbols_by_market(self, market):
            raise ConnectionError(f"Redis unavailable for {market}")

    input_path = tmp_path / "trades.csv"
    input_path.write_text("market,symbol\nspot,BTC\nperp,SOL\n")

    assert get_symbols_by_market_with_fallback(
        FailingRedisClient(),  # pyrefly: ignore
        "spot",
        input_path,
    ) == ["BTC"]


def test_get_symbols_by_market_falls_back_when_redis_is_empty(tmp_path):
    class EmptyRedisClient:
        def get_symbols_by_market(self, market):
            return []

    input_path = tmp_path / "trades.csv"
    input_path.write_text("market,symbol\nspot,BTC\nperp,SOL\n")

    assert get_symbols_by_market_with_fallback(
        EmptyRedisClient(),  # pyrefly: ignore
        "perp",
        input_path,
    ) == ["SOL"]
