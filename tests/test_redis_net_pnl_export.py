from __future__ import annotations

from src.utils.redis.net_pnl_export import (
    build_output_row,
    group_metric_keys,
    normalize_market,
    parse_pnl_key,
)


def test_parse_pnl_key_normalizes_market():
    assert parse_pnl_key("KUC4:BTC:Spot:NetRpnl") == (
        "spot",
        "KUC4",
        "BTC",
        "NetRpnl",
    )
    assert parse_pnl_key("BIN2:ETH:Future:NetUpnl") == (
        "perp",
        "BIN2",
        "ETH",
        "NetUpnl",
    )


def test_parse_pnl_key_rejects_unknown_metric():
    assert parse_pnl_key("KUC4:BTC:Spot:Unknown") is None


def test_normalize_market():
    assert normalize_market("Spot") == "spot"
    assert normalize_market("Future") == "perp"
    assert normalize_market("Margin") is None


def test_group_metric_keys_collects_relevant_metrics():
    grouped = group_metric_keys(
        [
            "KUC4:BTC:Spot:Buy",
            "KUC4:BTC:Spot:Sell",
            "KUC4:BTC:Spot:Trade",
            "KUC4:BTC:Spot:NetRpnl",
            "KUC4:BTC:Spot:Noise",
        ]
    )
    assert grouped[("spot", "KUC4", "BTC")] == {
        "Buy": "KUC4:BTC:Spot:Buy",
        "Sell": "KUC4:BTC:Spot:Sell",
        "Trade": "KUC4:BTC:Spot:Trade",
        "NetRpnl": "KUC4:BTC:Spot:NetRpnl",
    }


def test_build_output_row_uses_last_point_for_snapshot_metrics():
    data = {
        "buy": [[1, "10"], [2, "5"]],
        "sell": [[1, "4"]],
        "netpos": [[1, "3"], [2, "2"]],
        "rpnl": [[1, "7"], [2, "-2"]],
        "unpnl": [[1, "1.5"], [2, "0.5"]],
        "rpnlwfees": [[1, "4"]],
        "trade": [[1, "1"], [2, "1"], [3, "1"]],
    }

    def fetch_series(key: str | None):
        if key is None:
            return []
        return data[key]

    row = build_output_row(
        "spot",
        "KUC4",
        "BTC",
        {
            "Buy": "buy",
            "Sell": "sell",
            "Netpos": "netpos",
            "NetRpnl": "rpnl",
            "NetUpnl": "unpnl",
            "RpnlWFees": "rpnlwfees",
            "Trade": "trade",
        },
        fetch_series,
    )

    assert row == {
        "market": "spot",
        "strategy": "KUC4",
        "symbol": "BTC",
        "volume_$": 11.0,
        "net_position": 2.0,
        "net_position_$": 2.0,
        "rpnl": -2.0,
        "unpnl": 0.5,
        "rpnlwfees": 4.0,
        "npnl_r+un": -1.5,
        "npnl/volume_%": "-13.6364%",
        "trade_count": 1,
    }
