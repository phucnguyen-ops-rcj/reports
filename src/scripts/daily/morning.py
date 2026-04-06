from pathlib import Path

from src.utils.load_data import load_local_data
from src.utils.constants import THRESHOLDS, FINAL_COLUMNS, STRATEGY_NAME_MAPPING
from src.utils.dataframe import (
    aggregate_metric_columns,
    calculate_ratio_column,
    filter_rows_below_threshold,
    map_column_with_fallback,
)
from src.utils.report import build_daily_report, save_report


def build_group_summary(df, by_cols):
    summary_df = aggregate_metric_columns(df, by_cols, FINAL_COLUMNS)
    return calculate_ratio_column(summary_df, "npnl_r+un", "volume_$", "npnl/volume_%", scale=100)


def add_strategy_name(df, key_col):
    return map_column_with_fallback(df, key_col, "name", STRATEGY_NAME_MAPPING)


def main(file_path):
    df = load_local_data(file_path)
    total_npnl = df["npnl_r+un"].sum()

    # ===========by strategy==============
    strat_sum = build_group_summary(df, ["base_strategy"])
    loss_strats = filter_rows_below_threshold(
        strat_sum,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )

    strat_loss_df = df[df["base_strategy"].isin(loss_strats["base_strategy"])].copy()
    strat_detail = build_group_summary(strat_loss_df, ["base_strategy", "strategy"])
    strat_detail = add_strategy_name(strat_detail, "strategy")

    # ===========by symbol==============
    sym_sum = build_group_summary(df, ["mapped_symbol"])
    loss_sym_df = filter_rows_below_threshold(
        sym_sum,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )
    loss_symbols = loss_sym_df["mapped_symbol"].tolist()
    severe_sym_df = filter_rows_below_threshold(sym_sum, "npnl_r+un", -3000)
    severe_symbols = severe_sym_df["mapped_symbol"].tolist()

    # ==========deep dive into significant loss symbols===========
    sym_loss_df = df[df["mapped_symbol"].isin(loss_symbols)].copy()
    sym_strat_detail = build_group_summary(sym_loss_df, ["mapped_symbol", "strategy"])
    loss_sym_strats = filter_rows_below_threshold(
        sym_strat_detail,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )
    loss_sym_strats = add_strategy_name(loss_sym_strats, "strategy")

    # ==========make txt report===========
    report_text = build_daily_report(
        total_npnl,
        severe_symbols,
        loss_symbols,
        loss_strats,
        loss_sym_strats,
    )
    out_dir = Path(__file__).resolve().parents[3] / "results" / "daily" / "morning"
    out_path = save_report(report_text, out_dir)
    return loss_strats, strat_detail, loss_symbols, loss_sym_strats, out_path, report_text

if __name__ == "__main__":
    file_path = "data/analysis_data.csv"
    loss_strats, strat_detail, loss_symbols, loss_sym_strats, out_path, report_text = main(file_path)
    print(out_path)
    print()
    print(report_text)
