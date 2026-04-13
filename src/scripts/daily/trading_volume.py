from pathlib import Path
import logging
import pandas as pd
from src.settings import get_settings
from src.clients.signal import SignalClient
from src.utils.load_data import load_trading_volume_data
from src.utils.constants import REQUIREMENT_VOLUME
# from src.utils.format_message import build_trading_volume_report
from src.utils.save_data import save_csv
from src.utils.visualization import trading_volume_to_png_styled

logger = logging.getLogger(__name__)

FINAL_ORDER = [
    "product",
    "base",
    "requirement",
    "average_up_to_date",
    "last_24h_usd_volume",
    "total_usd_volume",
    "days_since_listing",
    "remaining_days",
    "meets_requirement",
]


def analyze_trading_volume(df):
    # group by base and product, sum usd_volume_24h, keep earliest timestamp per group
    volume_summary = df.groupby(["product", "base"]).agg({
        "timestamp_utc": "min",
        "usd_volume_24h": "sum",
    }).reset_index().rename(columns={"usd_volume_24h": "total_usd_volume"})
    volume_summary["days_since_listing"] = (pd.to_datetime("now") - pd.to_datetime(volume_summary["timestamp_utc"])).dt.days + 1
    volume_summary["remaining_days"] = 14 - volume_summary["days_since_listing"]
    volume_summary["average_up_to_date"] = volume_summary["total_usd_volume"] / volume_summary["days_since_listing"]

    # calculate last 24h volume from the most recent row per group
    last_24h_threshold = pd.to_datetime("now") - pd.Timedelta(days=1)
    last_24h_volume = (
        df[df["timestamp_utc"] >= last_24h_threshold]
        .groupby(["product", "base"])["usd_volume_24h"]
        .sum()
        .reset_index()
        .rename(columns={"usd_volume_24h": "last_24h_usd_volume"})
    )
    volume_summary = volume_summary.merge(last_24h_volume, on=["product", "base"], how="left").fillna({"last_24h_usd_volume": 0})
    volume_summary.drop(columns=["timestamp_utc"], inplace=True)  # no longer needed after computing days_since_listing

    # add requirement volume by exchange, base token, and product type
    # NOTE: if multiple exchanges are added in future, group by exchange and extend REQUIREMENT_VOLUME accordingly
    exchange_requirement_volume = REQUIREMENT_VOLUME.get("kucoin")
    volume_summary["requirement"] = volume_summary.apply(
        lambda row: exchange_requirement_volume[row["base"]][row["product"]],
        axis=1,
    )
    volume_summary = volume_summary[volume_summary["requirement"] > 0]  # exclude tokens with no requirement defined
    volume_summary["meets_requirement"] = volume_summary["average_up_to_date"] >= volume_summary["requirement"]

    # reorder columns and sort for consistent output
    volume_summary = volume_summary[FINAL_ORDER].sort_values(["product", "requirement", "base"]).reset_index(drop=True)
    return volume_summary


def _generate_and_send_report(report_text, volume_summary, out_dir, recipient=None, group_id=None):
    """Save CSV and PNG report files, and send only the PNG via Signal."""
    csv_path = save_csv(volume_summary, out_dir, prefix="daily_trading_volume")
    logger.info(f"CSV saved to: {csv_path}")

    png_path = trading_volume_to_png_styled(
        volume_summary,
        out_dir / "daily_trading_volume.png",
    )
    logger.info(f"PNG saved to: {png_path}")

    if recipient or group_id:
        try:
            client = SignalClient()
            send_kwargs = {"recipient": recipient, "group_id": group_id}
            client.send(report_text, attachments=png_path, **send_kwargs)  # send text + PNG attachment only
            logger.info("Trading volume report sent via Signal successfully.")
        except Exception as exc:
            logger.error(f"Failed to send Signal message: {exc}", exc_info=True)

    return png_path, csv_path


def main():
    app_settings = get_settings()
    logging.basicConfig(level=app_settings.log_level.upper(), format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        file_path = app_settings.trading_volume_input_path
        logger.info(f"Loading trading volume data from: {file_path}")
        df = load_trading_volume_data(app_settings.source, file_path)
    except FileNotFoundError:
        logger.error(f"Trading volume input file not found: {app_settings.trading_volume_input_path}")
        raise
    except Exception as exc:
        logger.error(f"Failed to load trading volume data: {exc}", exc_info=True)
        raise

    try:
        volume_summary = analyze_trading_volume(df)
        # report_text = build_trading_volume_report(volume_summary)
        logger.info("Trading volume report text built successfully.")
    except Exception as exc:
        logger.error(f"Failed to generate trading volume report: {exc}", exc_info=True)
        raise

    out_dir = Path(app_settings.output_dir) / "trading_volume"
    recipient = app_settings.signal_recipient
    group_id = app_settings.signal_group_id
    png_path, csv_path = _generate_and_send_report("Trading Volume Report", volume_summary, out_dir, recipient, group_id)

    return "", png_path, csv_path


if __name__ == "__main__":
    main()
