from src.clients.coingecko import CoinGeckoClient
from src.clients.signal import SignalClient
from src.settings import app_settings
from src.utils.format_message import build_market_summary_report
from pathlib import Path
import logging
from src.utils.save_data import save_report

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=app_settings.log_level.upper(), format='%(asctime)s - %(levelname)s - %(message)s')

    coingecko_client = CoinGeckoClient()
    summary = coingecko_client.get_global_market_summary()
    report = build_market_summary_report(summary)
    logger.info("Market summary report built successfully.")

    out_dir = Path(app_settings.output_dir) / "market"
    text_path = save_report(report, out_dir)
    logger.info(f"Report text saved to: {text_path}")
    print(report)

    if app_settings.enable_signal_notifications:
        recipient = app_settings.signal_recipient
        group_id = app_settings.signal_group_id
        if recipient or group_id:
            try:
                signal_client = SignalClient()
                send_kwargs = {"recipient": recipient, "group_id": group_id}
                signal_client.send(report, **send_kwargs)
                logger.info("Report sent via Signal successfully.")
            except Exception as exc:
                logger.error(f"Failed to send Signal message: {exc}", exc_info=True)

    return text_path


if __name__ == "__main__":
    text_path = main()
    print(f"Report saved to: {text_path}")
