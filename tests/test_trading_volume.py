from __future__ import annotations

import pandas as pd

import src.scripts.trading_volume as trading_volume


def test_analyze_trading_volume_preserves_configured_requirement(monkeypatch) -> None:
    monkeypatch.setattr(
        trading_volume,
        "REQUIREMENT_VOLUME",
        {"kucoin": {"GRAM": 10_000_000}},
    )
    df = pd.DataFrame(
        {
            "timestamp_utc": [
                pd.Timestamp("2026-01-01", tz="UTC"),
                pd.Timestamp("2026-06-16", tz="UTC"),
            ],
            "product": ["spot", "spot"],
            "base": ["GRAM", "GRAM"],
            "usd_volume_24h": [1_000_000.0, 2_000_000.0],
        }
    )

    result = trading_volume.analyze_trading_volume(df)

    assert result.loc[0, "requirement"] == 10_000_000
