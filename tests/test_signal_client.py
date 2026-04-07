from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

DEFAULT_SENDER = "+84559854979"
RECIPIENT = "+84906303607"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"


def _load_signal_client():
    client_path = Path(__file__).resolve().parents[1] / "src" / "signal-cli" / "client.py"
    spec = importlib.util.spec_from_file_location("signal_client", client_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.SignalClient


SignalClient = _load_signal_client()


@pytest.fixture(scope="module")
def client():
    sender = os.environ.get("SIGNAL_TEST_SENDER", DEFAULT_SENDER)
    if not sender:
        pytest.skip("Set SIGNAL_TEST_SENDER to run Signal integration tests.")

    base_url = os.environ.get("SIGNAL_TEST_BASE_URL", DEFAULT_BASE_URL)
    return SignalClient(sender=sender, base_url=base_url)


def _assert_send_response(response: dict) -> None:
    assert isinstance(response, dict)
    assert response
    assert any(key in response for key in ("timestamp", "messageId", "success", "message"))


def test_send_text_message_to_recipient(client):
    response = client.send("pytest text message", recipient=RECIPIENT)
    _assert_send_response(response)


def test_send_file_message_to_recipient(client, tmp_path: Path):
    attachment = tmp_path / "signal_test_attachment.txt"
    attachment.write_text("pytest attachment content", encoding="utf-8")

    response = client.send(attachment, recipient=RECIPIENT)
    _assert_send_response(response)
