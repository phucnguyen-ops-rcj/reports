import pandas as pd

from src.scripts.net_pnl import _analyze_large_profit_symbols
from src.utils.format_message import build_daily_report


def test_analyze_large_profit_symbols_sorts_highest_profit_first():
    df = pd.DataFrame(
        {
            "mapped_symbol": ["ETH", "H", "H", "XMR"],
            "volume_$": [1.0, 1.0, 1.0, 1.0],
            "npnl_r+un": [23_000.0, 15_000.0, 10_000.0, 20_000.0],
            "npnl/volume_%": [0.0, 0.0, 0.0, 0.0],
            "net_position_$": [0.0, 0.0, 0.0, 0.0],
            "unpnl": [0.0, 0.0, 0.0, 0.0],
            "rpnlwfees": [23_000.0, 15_000.0, 10_000.0, 20_000.0],
        }
    )

    assert _analyze_large_profit_symbols(df) == ["H", "ETH"]


def test_build_daily_report_includes_large_profit_symbols():
    report = build_daily_report(
        total_npnl=30_000.0,
        loss_base_strats=[],
        severe_symbols=[],
        large_profit_symbols=["H", "ETH"],
        loss_symbols=[],
        loss_sym_strats=pd.DataFrame(),
    )

    assert "Symbols with 24H NPNL > +20k: H / ETH" in report
