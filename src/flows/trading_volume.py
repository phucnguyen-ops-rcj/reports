import logging
from pathlib import Path

import pandas as pd
from prefect import flow, task
from typing import Literal, List
from src.scripts.trading_volume import analyze_trading_volume
from src.clients.signal import SignalClient
from src.settings import app_settings
from src.utils.load_data import load_trading_volume_data
from src.utils.save_data import save_csv
from src.utils.visualization import trading_volume_to_png_styled
from src.utils.constants import MONITORING_SYMBOLS

logger = logging.getLogger(__name__)


@task(name="Load trading volume data")
def task_load_data(
    source: Literal["api", "local"], input_path: str, symbols: List[str]
) -> pd.DataFrame:
    return load_trading_volume_data(source, input_path, symbols)


@task(name="Analyze trading volume")
def task_analyze(df: pd.DataFrame) -> pd.DataFrame:
    return analyze_trading_volume(df)


@task(name="Save volume report")
def task_save(volume_summary: pd.DataFrame, prefix: str = "") -> tuple:
    out_dir = Path(app_settings.output_dir) / "trading_volume"
    csv_path = save_csv(volume_summary, out_dir, prefix)
    logger.info(f"CSV saved to: {csv_path}")
    png_path = trading_volume_to_png_styled(
        volume_summary, out_dir / f"{prefix}_daily_trading_volume.png"
    )
    logger.info(f"PNG saved to: {png_path}")
    return png_path, csv_path


@task(name="Send volume via Signal", retries=1)
def task_send_signal(png_path: Path, prefix: str = "") -> None:
    if not app_settings.enable_signal_notifications:
        return
    recipient = app_settings.signal_recipient
    group_id = app_settings.signal_group_id
    if not (recipient or group_id):
        return
    # let exceptions propagate so Prefect marks this task FAILED in the UI
    client = SignalClient()
    client.send(
        f"Trading Volume Report - {prefix}",
        attachments=png_path,
        recipient=recipient,
        group_id=group_id,
    )
    logger.info("Trading volume report sent via Signal successfully.")


@flow(name="Trading Volume")
def trading_volume_flow(
    source: Literal["api", "local"] = app_settings.source,
    input_path: str = app_settings.trading_volume_input_path,
    symbols: List[str] = MONITORING_SYMBOLS,
) -> tuple:
    df: pd.DataFrame = task_load_data(source, input_path, symbols)
    volume_summary: pd.DataFrame = task_analyze(df)
    remaining_days_positive: pd.DataFrame = volume_summary[
        volume_summary["remaining_days"] > 0
    ].copy()
    listed_more_than_14_days: pd.DataFrame = volume_summary[
        volume_summary["remaining_days"].between(-30, 0, inclusive="both")
    ].copy()
    png_path = None
    csv_path = None
    for df_data, prefix in [
        (remaining_days_positive, "Remaining days > 0"),
        (listed_more_than_14_days, "Listed more than 14 days"),
    ]:
        if df_data.empty:
            logger.info(f"Skipping {prefix} report because it has no rows.")
            continue
        png_path, csv_path = task_save(df_data, prefix)  # pyrefly: ignore
        try:
            task_send_signal(png_path, prefix)
        except Exception:
            pass  # non-fatal; Prefect has recorded the task as FAILED in the UI
    return png_path, csv_path
