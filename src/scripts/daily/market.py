from src.clients.coingecko import CoinGeckoClient
from src.settings import get_settings
from src.utils.format_message import build_market_summary_report
from pathlib import Path
import importlib.util
from src.utils.save_data import save_report

def _load_signal_client():
    client_path = Path(__file__).resolve().parents[2] / "clients" / "signal.py"
    spec = importlib.util.spec_from_file_location("signal_client", client_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.SignalClient


def main():
    app_settings = get_settings()
    client = CoinGeckoClient()
    summary = client.get_global_market_summary()
    report = build_market_summary_report(summary)
    out_dir = Path(__file__).resolve().parents[3] / "results" / "daily"
    text_path = save_report(report, out_dir)
    print(report)
    # send report via Signal
    recipient = app_settings.signal_recipient
    group_id = app_settings.signal_group_id
    if recipient or group_id:
        SignalClient = _load_signal_client()
        client = SignalClient()
        send_kwargs = {"recipient": recipient, "group_id": group_id}
        client.send(report, **send_kwargs)
    return text_path


if __name__ == "__main__":
    text_path = main()
    print(f"Report saved to: {text_path}")
