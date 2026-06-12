import logging
from pathlib import Path

import pandas as pd
from prefect import flow, task
from typing import Literal
from src.scripts.net_pnl import (
    _analyze_base_strategy_losses,
    _analyze_large_profit_symbols,
    _analyze_symbol_losses,
    _build_final_table,
    _build_strategy_summary_table,
    _build_symbol_strategy_detail,
)
from src.clients.signal import SignalClient
from src.settings import app_settings
from src.utils.format_message import build_daily_report
from src.utils.load_data import load_pnl_data
from src.utils.save_data import save_report, save_csv
from src.utils.visualization import net_pnl_to_png_styled

logger = logging.getLogger(__name__)


@task(name="Load PnL data")
def task_load_data(source: Literal["api", "local"], input_path: str) -> pd.DataFrame:
    return load_pnl_data(source, input_path)


@task(name="Analyze PnL")
def task_analyze(df: pd.DataFrame) -> tuple:
    total_npnl = df["npnl_r+un"].sum()
    loss_base_strats = _analyze_base_strategy_losses(df)
    w_category_strat_sum_df = _build_strategy_summary_table(df)
    loss_sym_df, loss_symbols, severe_symbols = _analyze_symbol_losses(df)
    large_profit_sym_df, large_profit_symbols = _analyze_large_profit_symbols(df)
    final_df = _build_final_table(
        w_category_strat_sum_df,
        loss_sym_df,
        large_profit_sym_df,
    )
    loss_sym_strats = _build_symbol_strategy_detail(df, loss_symbols)
    report_text = build_daily_report(
        total_npnl,
        loss_base_strats,
        severe_symbols,
        large_profit_symbols,
        loss_symbols,
        loss_sym_strats,
    )
    return report_text, final_df


@task(name="Save PnL report")
def task_save(report_text: str, final_df: pd.DataFrame) -> tuple:
    out_dir = Path(app_settings.output_dir) / "net_pnl"
    text_path = save_report(report_text, out_dir)
    logger.info(f"Report text saved to: {text_path}")
    csv_path = save_csv(final_df, out_dir, prefix="")
    logger.info(f"CSV saved to: {csv_path}")
    png_path = net_pnl_to_png_styled(
        final_df, out_dir / "daily_net_pnl_by_strategy.png", highlight_col="npnl_r+un"
    )
    logger.info(f"PNG saved to: {png_path}")
    return png_path, csv_path, text_path


@task(name="Send PnL via Signal", retries=1)
def task_send_signal(report_text: str, png_path: Path) -> None:
    if not app_settings.enable_signal_notifications:
        return
    recipient = app_settings.signal_recipient
    group_id = app_settings.signal_group_id
    if not (recipient or group_id):
        return
    # let exceptions propagate so Prefect marks this task FAILED in the UI
    client = SignalClient()
    client.send(
        report_text, attachments=png_path, recipient=recipient, group_id=group_id
    )
    logger.info("PnL report sent via Signal successfully.")


@flow(name="Net PnL")
def net_pnl_flow(
    source: Literal["api", "local"] = app_settings.source,
    input_path: str = app_settings.net_pnl_input_path,
) -> tuple:
    df = task_load_data(source, input_path)
    report_text, final_df = task_analyze(df)
    png_path, csv_path, text_path = task_save(report_text, final_df)
    try:
        task_send_signal(report_text, png_path)
    except Exception:
        pass  # non-fatal; Prefect has recorded the task as FAILED in the UI
    return png_path, csv_path, text_path
