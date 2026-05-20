from __future__ import annotations

import socket
import urllib.error
from types import SimpleNamespace

import pytest

from src.clients.ops_api import OpsApiClient, OpsApiResponse
from src.flows.ops import build_ops_signal_message, call_ops_api_task


def test_local_ops_request_returns_transport_failure_on_url_error(monkeypatch):
    def fake_urlopen(*args, **kwargs):
        raise urllib.error.URLError(socket.timeout("timed out"))

    monkeypatch.setattr("src.clients.ops_api.urllib.request.urlopen", fake_urlopen)
    client = OpsApiClient(execution_mode="local")

    response = client.request(
        method="GET",
        endpoint="/health",
        payload={},
        authenticated=False,
    )

    assert response.status == 0
    assert response.body == "request transport failed: timed out"


def test_call_ops_api_task_raises_transport_failure_with_original_error(monkeypatch):
    def fake_request(self, method, endpoint, payload, authenticated):
        return OpsApiResponse(
            endpoint=endpoint,
            status=0,
            body="curl failed with exit 28: Operation timed out",
            payload=payload,
        )

    monkeypatch.setattr("src.flows.ops.OpsApiClient.request", fake_request)
    monkeypatch.setattr(
        "src.flows.ops.get_run_logger",
        lambda: SimpleNamespace(info=lambda *args, **kwargs: None),
    )

    with pytest.raises(RuntimeError) as exc_info:
        call_ops_api_task.fn(
            endpoint="/get_stacker_accepted_orders",
            payload={"symbol": "HOOLI-USDT"},
        )

    assert (
        str(exc_info.value)
        == "/get_stacker_accepted_orders transport failed: curl failed with exit 28: Operation timed out"
    )


def test_call_ops_api_task_sends_cleaned_strategy_message_to_signal_group(monkeypatch):
    captured: dict[str, str] = {}
    logged: dict[str, str] = {}
    body = """Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 6.5.0-1023-aws x86_64)

*** System restart required ***
✅ success"""

    def fake_request(self, method, endpoint, payload, authenticated):
        return OpsApiResponse(
            endpoint=endpoint,
            status=200,
            body=body,
            payload=payload,
        )

    class FakeSignalClient:
        def send(self, message, *, recipient=None, group_id=None, attachments=None):
            captured["message"] = message
            captured["group_id"] = group_id  # pyrefly: ignore
            captured["recipient"] = recipient or ""
            return {"success": True}

    monkeypatch.setattr("src.flows.ops.OpsApiClient.request", fake_request)
    monkeypatch.setattr(
        "src.flows.ops.get_run_logger",
        lambda: SimpleNamespace(
            info=lambda fmt, *args: logged.setdefault("response", args[0])
            if fmt == "Response:\n%s"
            else None,
            error=lambda *args, **kwargs: None,
        ),
    )
    monkeypatch.setattr("src.flows.ops.SignalClient", FakeSignalClient)
    monkeypatch.setattr("src.flows.ops.app_settings.enable_signal_notifications", True)
    monkeypatch.setattr("src.flows.ops.app_settings.signal_group_id", "group.test")

    response = call_ops_api_task.fn(
        endpoint="/get_stacker_accepted_orders",
        payload={"symbol": "ATWO-USDT"},
        send_signal_to_group=True,
    )

    assert response["status"] == 200
    assert logged["response"] == body.rstrip()
    assert captured == {
        "message": """Checked stacker status

Payload:
{
  "symbol": "ATWO-USDT"
}

API response:
✅ success""",
        "group_id": "group.test",
        "recipient": "",
    }


def test_build_ops_signal_message_for_stacker_launch():
    message = build_ops_signal_message(
        "/launch_stacker",
        {
            "base_ccy": "ATWO",
            "quote_ccy": "USDT",
            "stacker_level": 4,
        },
        "folder created\nFound: kucoincpp\nAll commands executed.",
    )

    assert (
        message
        == """Started stacker

Payload:
{
  "base_ccy": "ATWO",
  "quote_ccy": "USDT",
  "stacker_level": 4
}

API response:
folder created
Found: kucoincpp
All commands executed."""
    )
