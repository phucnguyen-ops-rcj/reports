from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.clients.signal import SignalClient
from src.settings import get_settings


def _get_test_settings():
    app_settings = get_settings()
    sender = os.environ.get("SIGNAL_TEST_SENDER", app_settings.signal_sender)
    recipient = os.environ.get("SIGNAL_TEST_RECIPIENT", app_settings.signal_recipient)
    base_url = os.environ.get("SIGNAL_TEST_BASE_URL", app_settings.signal_base_url)
    return sender, recipient, base_url


@pytest.fixture(scope="module")
def client():
    sender, _, base_url = _get_test_settings()
    if not sender:
        pytest.skip("Set SIGNAL_TEST_SENDER (or SIGNAL_SENDER in .env) to run Signal integration tests.")
    return SignalClient(sender=sender, base_url=base_url)


@pytest.fixture(scope="module")
def recipient():
    _, recipient, _ = _get_test_settings()
    if not recipient:
        pytest.skip("Set SIGNAL_TEST_RECIPIENT (or SIGNAL_RECIPIENT in .env) to run Signal integration tests.")
    return recipient


def _assert_send_response(response: dict) -> None:
    assert isinstance(response, dict)
    assert response
    assert any(key in response for key in ("timestamp", "messageId", "success", "message"))


def test_send_text_message_to_recipient(client, recipient):
    response = client.send("pytest text message", recipient=recipient)
    _assert_send_response(response)


def test_send_file_message_to_recipient(client, recipient, tmp_path: Path):
    attachment = tmp_path / "signal_test_attachment.txt"
    attachment.write_text("pytest attachment content", encoding="utf-8")

    response = client.send(attachment, recipient=recipient)
    _assert_send_response(response)


def test_send_text_and_file_message_to_recipient(client, recipient, tmp_path: Path):
    attachment = tmp_path / "signal_test_attachment.txt"
    attachment.write_text("pytest attachment content", encoding="utf-8")

    response = client.send("pytest text with attachment", attachments=attachment, recipient=recipient)
    _assert_send_response(response)
