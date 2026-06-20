import pandas as pd

from src.scripts.net_pnl import (
    _analyze_large_profit_symbols,
    _analyze_symbol_losses,
    _build_png_table,
    _build_final_table,
)
from src.utils.format_message import build_daily_report


def test_analyze_large_profit_symbols_sorts_highest_profit_first():
    df = pd.DataFrame(
        {
            "mapped_symbol": ["ETH", "H", "H", "H", "XMR", "SOL"],
            "strategy": [
                "strategy3",
                "strategy3",
                "strategy4",
                "strategy5",
                "strategy4",
                "strategy4",
            ],
            "volume_$": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "npnl_r+un": [
                23_000.0,
                15_000.0,
                6_000.4,
                4_000.0,
                20_000.0,
                5_000.0,
            ],
            "npnl/volume_%": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "net_position_$": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "unpnl": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "rpnlwfees": [
                23_000.0,
                15_000.0,
                6_000.4,
                4_000.0,
                20_000.0,
                5_000.0,
            ],
        }
    )

    large_profit_sym_df, large_profit_symbols = _analyze_large_profit_symbols(df)

    assert large_profit_symbols == ["H", "ETH", "XMR"]
    assert large_profit_sym_df["npnl_r+un"].tolist() == [25_000.4, 23_000.0, 20_000.0]
    assert large_profit_sym_df["category"].tolist() == [
        ["s3", "s4"],
        ["s3"],
        ["s4"],
    ]
    assert large_profit_sym_df["category_total_npnl"].tolist() == [
        [15_000, 6_000],
        [23_000],
        [20_000],
    ]


def test_analyze_symbol_losses_includes_strategy_breakdown():
    df = pd.DataFrame(
        {
            "mapped_symbol": ["ETH", "ETH", "ETH", "BTC"],
            "strategy": ["strategy9-2", "strategy4", "kucc4", "strategy3"],
            "volume_$": [1.0, 1.0, 1.0, 1.0],
            "npnl_r+un": [-1_400.4, -1_600.6, -1_200.2, 500.0],
            "npnl/volume_%": [0.0, 0.0, 0.0, 0.0],
            "net_position_$": [0.0, 0.0, 0.0, 0.0],
            "unpnl": [0.0, 0.0, 0.0, 0.0],
            "rpnlwfees": [-1_400.4, -1_600.6, -1_200.2, 500.0],
        }
    )

    loss_sym_df, loss_symbols, severe_symbols = _analyze_symbol_losses(df)

    assert loss_symbols == ["ETH"]
    assert severe_symbols == ["ETH"]
    assert loss_sym_df["category"].tolist() == [["k4", "s4", "s9-2"]]
    assert loss_sym_df["category_total_npnl"].tolist() == [[-1_200, -1_601, -1_400]]


def test_build_final_table_includes_large_profit_symbols():
    strategy_summary_df = pd.DataFrame(
        {"strategy": ["strategy8"], "npnl_r+un": [30_000.0]}
    )
    loss_sym_df = pd.DataFrame({"mapped_symbol": ["ESPORTS"], "npnl_r+un": [-3_100.0]})
    large_profit_sym_df = pd.DataFrame(
        {"mapped_symbol": ["H", "ETH"], "npnl_r+un": [25_000.0, 23_000.0]}
    )

    final_df = _build_final_table(strategy_summary_df, loss_sym_df, large_profit_sym_df)

    assert final_df["strategy"].tolist() == ["strategy8", "ESPORTS", "H", "ETH"]


def test_build_png_table_formats_only_scalar_category_total_npnl():
    final_df = pd.DataFrame(
        {
            "strategy": ["strategy1", "ETH"],
            "category_total_npnl": [-10_365.040000000003, [-1_200, -1_601]],
        }
    )

    png_df = _build_png_table(final_df)

    assert png_df["category_total_npnl"].tolist() == [
        "-10,365.04",
        [-1_200, -1_601],
    ]
    assert final_df["category_total_npnl"].tolist() == [
        -10_365.040000000003,
        [-1_200, -1_601],
    ]


def test_build_daily_report_includes_large_profit_symbols():
    report = build_daily_report(
        total_npnl=30_000.0,
        loss_base_strats=[],
        severe_symbols=[],
        large_profit_symbols=["H", "ETH"],
        loss_symbols=[],
        loss_sym_strats=pd.DataFrame(),
    )

    assert "Symbols with 24H NPNL > +5k: H / ETH" in report
