from __future__ import annotations

import socket
import urllib.error
from types import SimpleNamespace

import pytest

from src.clients.ops_api import OpsApiClient, OpsApiResponse
from src.flows.ops import (
    build_ops_signal_message,
    call_ops_api_task,
    mirror_control_flow,
    stacker_launch_flow,
    start_volume_strategy_flow,
)


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
✅ success
==================================================================
kucoincpp_ATWO_USDT_twkpi_st_1.txtpb.INFO:
NEW_ORDER_STATUS_ACCEPTED = 26
OnGatewayMessage new_order_response { status: NEW_ORDER_STATUS_ACCEPTED order_id: 1782127219110786 }
NEW_ORDER_STATUS_REJECTED = 0"""

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
        "message": """kucoincpp_ATWO_USDT_twkpi_st_1.txtpb.INFO:
NEW_ORDER_STATUS_ACCEPTED = 26
NEW_ORDER_STATUS_REJECTED = 0""",
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


def test_stacker_launch_flow_checks_status_after_delay(monkeypatch):
    calls: list[dict[str, object]] = []
    sleeps: list[int] = []

    def fake_call_ops_api_task(**kwargs):
        calls.append(kwargs)
        return {"status": 200, "endpoint": kwargs["endpoint"]}

    monkeypatch.setattr("src.flows.ops.call_ops_api_task", fake_call_ops_api_task)
    monkeypatch.setattr(
        "src.flows.ops.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    monkeypatch.setattr(
        "src.flows.ops.get_run_logger",
        lambda: SimpleNamespace(info=lambda *args, **kwargs: None),
    )

    response = stacker_launch_flow.fn("ARX-USDT", stacker_level=2)

    assert response == {"status": 200, "endpoint": "/launch_stacker"}
    assert sleeps == [10]
    assert [call["endpoint"] for call in calls] == [
        "/launch_stacker",
        "/get_stacker_accepted_orders",
    ]
    assert calls[0]["payload"] == {
        "base_ccy": "ARX",
        "quote_ccy": "USDT",
        "stacker_level": 2,
    }
    assert calls[1]["payload"] == {"symbol": "ARX-USDT"}
    assert calls[0]["send_signal_to_group"] is True
    assert calls[1]["send_signal_to_group"] is True


def test_stacker_launch_flow_includes_non_blank_box(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_call_ops_api_task(**kwargs):
        calls.append(kwargs)
        return {"status": 200, "endpoint": kwargs["endpoint"]}

    monkeypatch.setattr("src.flows.ops.call_ops_api_task", fake_call_ops_api_task)
    monkeypatch.setattr("src.flows.ops.time.sleep", lambda seconds: None)
    monkeypatch.setattr(
        "src.flows.ops.get_run_logger",
        lambda: SimpleNamespace(info=lambda *args, **kwargs: None),
    )

    stacker_launch_flow.fn("ARX-USDT", stacker_level=2, box=" T11 ")

    assert calls[0]["payload"] == {
        "base_ccy": "ARX",
        "quote_ccy": "USDT",
        "stacker_level": 2,
        "box": "T11",
    }
    assert calls[1]["payload"] == {
        "symbol": "ARX-USDT",
        "box": "T11",
    }


def test_start_volume_strategy_flow_checks_fills_after_delay(monkeypatch):
    calls: list[dict[str, object]] = []
    sleeps: list[int] = []

    def fake_call_ops_api_task(**kwargs):
        calls.append(kwargs)
        return {"status": 200, "endpoint": kwargs["endpoint"]}

    monkeypatch.setattr("src.flows.ops.call_ops_api_task", fake_call_ops_api_task)
    monkeypatch.setattr(
        "src.flows.ops.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    monkeypatch.setattr(
        "src.flows.ops.get_run_logger",
        lambda: SimpleNamespace(info=lambda *args, **kwargs: None),
    )

    response = start_volume_strategy_flow.fn("ARX-USDT")

    assert response == {"status": 200, "endpoint": "/start_volume_strategy"}
    assert sleeps == [60]
    assert [call["endpoint"] for call in calls] == [
        "/start_volume_strategy",
        "/get_volume_strategy_fills",
    ]
    assert calls[0]["payload"] == {
        "base_currency": "ARX",
        "quote_currency": "USDT",
    }
    assert calls[1]["payload"] == {
        "base_currency": "ARX",
        "quote_currency": "USDT",
    }
    assert calls[0]["send_signal_to_group"] is True
    assert calls[1]["send_signal_to_group"] is True


def test_start_volume_strategy_flow_includes_box_in_both_requests(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_call_ops_api_task(**kwargs):
        calls.append(kwargs)
        return {"status": 200, "endpoint": kwargs["endpoint"]}

    monkeypatch.setattr("src.flows.ops.call_ops_api_task", fake_call_ops_api_task)
    monkeypatch.setattr("src.flows.ops.time.sleep", lambda seconds: None)
    monkeypatch.setattr(
        "src.flows.ops.get_run_logger",
        lambda: SimpleNamespace(info=lambda *args, **kwargs: None),
    )

    start_volume_strategy_flow.fn("ARX-USDT", box=" T11 ")

    expected_payload = {
        "base_currency": "ARX",
        "quote_currency": "USDT",
        "box": "T11",
    }
    assert calls[0]["payload"] == expected_payload
    assert calls[1]["payload"] == expected_payload


def test_mirror_control_flow_includes_non_blank_box(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_call_ops_api_task(**kwargs):
        calls.append(kwargs)
        return {"status": 200, "endpoint": kwargs["endpoint"]}

    monkeypatch.setattr("src.flows.ops.call_ops_api_task", fake_call_ops_api_task)

    mirror_control_flow.fn("ARX-USDT", box=" T11 ")

    assert calls[0]["endpoint"] == "/strategy_control"
    assert calls[0]["payload"] == {
        "method": "start",
        "name": "mirror_spot_listings_strat2_ARXUSDT",
        "box": "T11",
    }
