from __future__ import annotations

import pandas as pd

from src.scripts.net_pnl import _build_final_table


def test_build_final_table_fills_category_placeholders_for_loss_symbols():
    strategy_rows = pd.DataFrame(
        [
            {
                "strategy": "strategy1",
                "volume_$": 10.0,
                "npnl_r+un": 1.0,
                "npnl/volume_%": 0.1,
                "net_position_$": 2.0,
                "unpnl": 3.0,
                "rpnlwfees": 4.0,
                "category": "Quoting",
                "category_total_npnl": 1.0,
            }
        ]
    )
    loss_symbol_rows = pd.DataFrame(
        [
            {
                "mapped_symbol": "BLUAI",
                "volume_$": 20.0,
                "npnl_r+un": -5.0,
                "npnl/volume_%": -0.25,
                "net_position_$": 6.0,
                "unpnl": -7.0,
                "rpnlwfees": 8.0,
            }
        ]
    )

    result = _build_final_table(strategy_rows, loss_symbol_rows)

    assert result.to_dict("records")[1]["strategy"] == "BLUAI"
    assert result.to_dict("records")[1]["category"] == "-"
    assert result.to_dict("records")[1]["category_total_npnl"] == 0.0
