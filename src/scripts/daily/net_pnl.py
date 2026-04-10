from pathlib import Path
import importlib.util
import pandas as pd
from src.settings import get_settings
from src.utils.load_data import load_local_data
from src.utils.constants import THRESHOLDS, FINAL_COLUMNS, STRATEGY_NAME_MAPPING, STRATEGY_CATEGORY_MAPPING
from src.utils.dataframe import (
    aggregate_metric_columns,
    calculate_ratio_column,
    filter_rows_below_threshold,
    map_column_with_fallback,
)
from src.utils.format_message import build_daily_report
from src.utils.save_data import save_report, save_csv
from src.utils.visualization import dataframe_to_png_styled

def _load_signal_client():
    client_path = Path(__file__).resolve().parents[2] / "clients" / "signal.py"
    spec = importlib.util.spec_from_file_location("signal_client", client_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.SignalClient


def build_group_summary(df, by_cols):
    summary_df = aggregate_metric_columns(df, by_cols, FINAL_COLUMNS[1:])
    return calculate_ratio_column(summary_df, "npnl_r+un", "volume_$", "npnl/volume_%", scale=100)


def add_strategy_name(df, key_col):
    return map_column_with_fallback(df, key_col, "name", STRATEGY_NAME_MAPPING)

def add_strategy_category(df, key_col):
    return map_column_with_fallback(df, key_col, "category", STRATEGY_CATEGORY_MAPPING)


def _analyze_base_strategy_losses(df):
    """Identify base strategies with losses."""
    base_strat_sum = build_group_summary(df, ["base_strategy"])
    loss_base_strats_df = filter_rows_below_threshold(
        base_strat_sum,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )
    return loss_base_strats_df["base_strategy"].tolist()


def _build_strategy_summary_table(df):
    """Build strategy summary with categories and total row."""
    strat_sum = build_group_summary(df, ["strategy"])
    w_category_strat_sum_df = add_strategy_category(strat_sum, "strategy")
    w_category_strat_sum_df["category_total_npnl"] = w_category_strat_sum_df.groupby("category")["npnl_r+un"].transform("sum")
    w_category_strat_sum_df = calculate_ratio_column(w_category_strat_sum_df, "npnl_r+un", "volume_$", "npnl/volume_%", scale=100)
    w_category_strat_sum_df.sort_values(["category_total_npnl", "strategy"], inplace=True, ascending=[True, True])
    category_total_npnl_sum = (
        w_category_strat_sum_df
        .drop_duplicates(subset=["category"])["category_total_npnl"]
        .sum()
    )
    
    _total_row = pd.DataFrame({
        "strategy": ["Total"],
        "volume_$": [w_category_strat_sum_df["volume_$"].sum()],
        "npnl_r+un": [w_category_strat_sum_df["npnl_r+un"].sum()],
        "npnl/volume_%": [round(w_category_strat_sum_df["npnl_r+un"].sum() / strat_sum["volume_$"].sum() * 100, 2)],
        "net_position_$": [w_category_strat_sum_df["net_position_$"].sum()],
        "unpnl": [w_category_strat_sum_df["unpnl"].sum()],
        "rpnlwfees": [w_category_strat_sum_df["rpnlwfees"].sum()],
        "category": ["-"],
        "category_total_npnl": [category_total_npnl_sum],
    })
    return pd.concat([w_category_strat_sum_df, _total_row], ignore_index=True)


def _analyze_symbol_losses(df):
    """Identify symbols with losses and severe losses."""
    sym_sum = build_group_summary(df, ["mapped_symbol"])
    loss_sym_df = filter_rows_below_threshold(
        sym_sum,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )
    loss_symbols = loss_sym_df["mapped_symbol"].tolist()
    severe_sym_df = filter_rows_below_threshold(sym_sum, "npnl_r+un", -3000)
    severe_symbols = severe_sym_df["mapped_symbol"].tolist()
    return loss_sym_df, loss_symbols, severe_symbols


def _build_symbol_strategy_detail(df, loss_symbols):
    """Deep dive into strategy-level details for loss symbols."""
    sym_loss_df = df[df["mapped_symbol"].isin(loss_symbols)].copy()
    sym_strat_detail = build_group_summary(sym_loss_df, ["mapped_symbol", "strategy"])
    loss_sym_strats = filter_rows_below_threshold(
        sym_strat_detail,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )
    return loss_sym_strats


def _generate_and_send_report(report_text, final_df, out_dir, recipient=None, group_id=None):
    """Generate report files and send via signal client."""
    text_path = save_report(report_text, out_dir)
    csv_path = save_csv(final_df, out_dir, prefix="daily_net_pnl_by_strategy")
    png_path = dataframe_to_png_styled(
        final_df, 
        out_dir / "daily_net_pnl_by_strategy.png",
        highlight_col="npnl_r+un"
    )

    if recipient or group_id:
        SignalClient = _load_signal_client()
        client = SignalClient()
        send_kwargs = {"recipient": recipient, "group_id": group_id}
        client.send(report_text, attachments=png_path, **send_kwargs)
    
    return png_path, csv_path, text_path


def main():
    app_settings = get_settings()
    file_path = "data/UI 10 April 0800H SG.csv"
    df = load_local_data(file_path)
    total_npnl = df["npnl_r+un"].sum()

    # Analyze base strategy losses
    loss_base_strats = _analyze_base_strategy_losses(df)
    
    # Build strategy summary table
    w_category_strat_sum_df = _build_strategy_summary_table(df)
    
    # Analyze symbol losses
    loss_sym_df, loss_symbols, severe_symbols = _analyze_symbol_losses(df)
    
    # Build final table
    final_df = pd.concat([w_category_strat_sum_df, loss_sym_df.rename(columns={"mapped_symbol": "strategy"})], ignore_index=True, sort=False)
    
    # Deep dive into symbol-strategy details
    loss_sym_strats = _build_symbol_strategy_detail(df, loss_symbols)

    # Generate report
    report_text = build_daily_report(
        total_npnl,
        loss_base_strats,
        severe_symbols,
        loss_symbols,
        loss_sym_strats,
    )
    
    # Generate and send report
    out_dir = Path(__file__).resolve().parents[3] / "results" / "daily"
    recipient = app_settings.signal_recipient
    group_id = app_settings.signal_group_id
    png_path, csv_path, text_path = _generate_and_send_report(report_text, final_df, out_dir, recipient, group_id)

    return report_text, png_path, csv_path, text_path


if __name__ == "__main__":
    main()
