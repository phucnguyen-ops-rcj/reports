import logging
from pathlib import Path

from prefect import flow, task

from src.clients.third_parties.coingecko import CoinGeckoClient
from src.clients.signal import SignalClient
from src.settings import app_settings
from src.utils.format_message import build_market_summary_report
from src.utils.save_data import save_report

logger = logging.getLogger(__name__)


@task(name="Fetch market summary")
def fetch_market_summary() -> str:
    coingecko_client = CoinGeckoClient()
    summary = coingecko_client.get_global_market_summary()
    return build_market_summary_report(summary)


@task(name="Save market report")
def save_market_report(report: str) -> Path:
    out_dir = Path(app_settings.output_dir) / "market"
    text_path = save_report(report, out_dir)
    logger.info(f"Report text saved to: {text_path}")
    return text_path


@task(name="Send market via Signal", retries=1)
def send_market_signal(report: str) -> None:
    if not app_settings.enable_signal_notifications:
        return
    recipient = app_settings.signal_recipient
    group_id = app_settings.signal_group_id
    if not (recipient or group_id):
        return
    # let exceptions propagate so Prefect marks this task FAILED in the UI
    client = SignalClient()
    client.send(report, recipient=recipient, group_id=group_id)
    logger.info("Market report sent via Signal successfully.")


@flow(name="Market")
def market_flow() -> Path:
    report = fetch_market_summary()
    text_path = save_market_report(report)
    try:
        send_market_signal(report)
    except Exception:
        pass  # non-fatal; Prefect has recorded the task as FAILED in the UI
    return text_path
