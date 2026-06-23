from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from prefect import flow, task
from prefect.logging import get_run_logger

from src.clients.ops_api import (
    DEFAULT_OPS_BASE_ENDPOINT,
    DEFAULT_OPS_EXECUTION_MODE,
    DEFAULT_OPS_SSH_HOST,
    DEFAULT_OPS_TIMEOUT_SECONDS,
    OpsApiClient,
    base_from_symbol,
    normalize_symbol,
)
from src.clients.signal import SignalClient
from src.scripts.new_listing import load_config, resolve_config_path, run_new_listing
from src.settings import app_settings
from src.utils.ops_response import format_ops_response_body

STACKER_STATUS_DELAY_SECONDS = 10
VOLUME_FILLS_DELAY_SECONDS = 60


def parse_json_object(value: str, parameter_name: str) -> dict[str, Any]:
    if not value.strip():
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{parameter_name} must be a JSON object.")
    return parsed


@task(name="Call RCJ ops API")
def call_ops_api_task(
    endpoint: str,
    payload: dict[str, Any],
    method: Literal["GET", "POST"] = "POST",
    authenticated: bool = True,
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
    fail_on_error: bool = True,
    send_signal_to_group: bool = False,
) -> dict[str, Any]:
    logger = get_run_logger()
    logger.info("%s %s", method, endpoint)
    logger.info("Execution mode: %s", execution_mode)
    if execution_mode == "ssh":
        logger.info("SSH host: %s", ssh_host)
    logger.info("Payload:\n%s", json.dumps(payload, indent=2, sort_keys=True))

    client = OpsApiClient(
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
    )
    response = client.request(
        method=method,
        endpoint=endpoint,
        payload=payload,
        authenticated=authenticated,
    )
    logger.info("HTTP %s", response.status)
    logger.info("Response:\n%s", response.body.rstrip())
    print(f"HTTP {response.status}")
    print(response.body.rstrip())

    if response.ok and send_signal_to_group:
        send_ops_signal_to_group(
            endpoint,
            payload,
            format_ops_response_body(endpoint, response.body),
            logger,
        )

    if fail_on_error and not response.ok:
        if response.status == 0:
            raise RuntimeError(f"{endpoint} transport failed: {response.body}")
        raise RuntimeError(f"{endpoint} failed with HTTP {response.status}.")
    return response.as_dict()


def send_ops_signal_to_group(
    endpoint: str,
    payload: dict[str, Any],
    response_body: str,
    logger: Any,
) -> None:
    if not app_settings.enable_signal_notifications:
        return
    group_id = app_settings.signal_group_id
    if not group_id:
        return

    message = build_ops_signal_message(endpoint, payload, response_body)
    client = SignalClient()
    try:
        client.send(message, group_id=group_id)
    except Exception:
        logger.error("Signal send failed for %s", endpoint, exc_info=True)
        return
    logger.info("Ops API response sent to Signal group for %s", endpoint)


def build_ops_signal_message(
    endpoint: str,
    payload: dict[str, Any],
    response_body: str,
) -> str:
    if endpoint == "/get_stacker_accepted_orders":
        return response_body

    payload_json = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    return (
        f"{describe_ops_signal_action(endpoint, payload)}\n\n"
        f"Payload:\n{payload_json}\n\n"
        f"API response:\n{response_body}"
    )


def describe_ops_signal_action(endpoint: str, payload: dict[str, Any]) -> str:
    if endpoint == "/start_volume_strategy":
        return "Started volume strategy"
    if endpoint == "/launch_stacker":
        return "Started stacker"
    if endpoint == "/start_volatility_model":
        return "Started volatility model"
    if endpoint == "/get_stacker_accepted_orders":
        return "Checked stacker status"
    if endpoint == "/get_volume_strategy_fills":
        return "Checked volume strategy fills"
    if endpoint == "/setup_stacker_config":
        return "Set up stacker config"
    if endpoint == "/update_stacker_config":
        return "Updated stacker config"
    if endpoint in {"/gateway_control", "/feed_control", "/strategy_control"}:
        component_names = {
            "/gateway_control": "mirror gateway",
            "/feed_control": "mirror feed",
            "/strategy_control": "mirror strategy",
        }
        verb = past_tense_action(str(payload.get("method", "")))
        return f"{verb} {component_names[endpoint]}"
    return f"RCJ ops API {endpoint}"


def past_tense_action(action: str) -> str:
    normalized = action.strip().lower()
    mapping = {
        "start": "Started",
        "stop": "Stopped",
        "restart": "Restarted",
    }
    return mapping.get(normalized, normalized.title() or "Ran")


def build_volume_strategy_payload(symbol: str, quote_ccy: str) -> dict[str, Any]:
    return {
        "base_currency": base_from_symbol(symbol, quote_ccy),
        "quote_currency": quote_ccy.upper(),
    }


def build_stacker_status_payload(symbol: str, quote_ccy: str) -> dict[str, Any]:
    return {"symbol": normalize_symbol(symbol, quote_ccy)}


@flow(name="Ops API Request", log_prints=True)
def ops_api_request_flow(
    endpoint: str,
    payload_json: str = "{}",
    method: Literal["GET", "POST"] = "POST",
    authenticated: bool = True,
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
    fail_on_error: bool = True,
) -> dict[str, Any]:
    payload = parse_json_object(payload_json, "payload_json")
    return call_ops_api_task(
        endpoint=endpoint,
        payload=payload,
        method=method,
        authenticated=authenticated,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        fail_on_error=fail_on_error,
    )


@flow(name="Ops Health Check", log_prints=True)
def ops_health_flow(
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    return call_ops_api_task(
        endpoint="/health",
        payload={},
        method="GET",
        authenticated=False,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
    )


@flow(name="Ops Get Balance", log_prints=True)
def ops_get_balance_flow(
    exchange: str,
    account: str = "main",
    token: str = "USDT",
    market: str = "",
    extra_payload_json: str = "{}",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload = {
        "exchange": exchange,
        "account": account,
        "token": token.upper(),
    }
    if market:
        payload["market"] = market
    payload.update(parse_json_object(extra_payload_json, "extra_payload_json"))
    return call_ops_api_task(
        endpoint="/get-balance",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
    )


@flow(name="Ops Run Transfer", log_prints=True)
def ops_run_transfer_flow(
    mode: str,
    token: str,
    from_exchange: str,
    amount: float,
    sub_account_name: str = "",
    to_exchange: str = "",
    extra_payload_json: str = "{}",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": mode,
        "token": token.upper(),
        "from_exchange": from_exchange,
        "amount": amount,
    }
    if sub_account_name:
        payload["sub_account_name"] = sub_account_name
    if to_exchange:
        payload["to_exchange"] = to_exchange
    payload.update(parse_json_object(extra_payload_json, "extra_payload_json"))
    return call_ops_api_task(
        endpoint="/run-transfer",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
    )


@flow(name="Ops Run Monitor", log_prints=True)
def ops_run_monitor_flow(
    update_time: int = 10,
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = 30,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    return call_ops_api_task(
        endpoint="/run-monitor",
        payload={"update_time": update_time},
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
    )


@flow(name="New Listing Setup", log_prints=True)
def new_listing_flow(
    symbol: str = "testing",
    config_path: str = "",
    dry_run: bool = True,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, str | bool]:
    logger = get_run_logger()
    args = SimpleNamespace(
        symbol=symbol if symbol else None,
        config=config_path if config_path else None,
    )
    resolved_path = resolve_config_path(args)  # pyrefly: ignore
    logger.info("Loading new-listing config from %s", resolved_path)
    config = load_config(Path(resolved_path))
    run_new_listing(
        config,
        dry_run=dry_run,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
    )
    return {
        "symbol": symbol,
        "config_path": str(resolved_path),
        "dry_run": dry_run,
        "execution_mode": execution_mode,
        "ssh_host": ssh_host,
    }


@flow(name="Start Volatility Model", log_prints=True)
def volatility_model_flow(
    symbol: str,
    market: Literal["spot", "perp"] = "spot",
    exchange: str = "kucoin",
    exchange_data: str = "kucoin",
    risk_tol: Literal["low", "medium", "high"] = "low",
    strategy: str = "slow_mm",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload = {
        "symbol": normalize_symbol(symbol),
        "market": market,
        "exchange": exchange,
        "exchange_data": exchange_data,
        "risk_tol": risk_tol,
        "strategy": strategy,
    }
    return call_ops_api_task(
        endpoint="/start_volatility_model",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )


@flow(name="Volume Strategy Fills", log_prints=True)
def volume_strategy_fills_flow(
    symbol: str,
    date: str = "",
    quote_ccy: str = "USDT",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload = build_volume_strategy_payload(symbol, quote_ccy)
    if date:
        payload["date"] = date
    return call_ops_api_task(
        endpoint="/get_volume_strategy_fills",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )


@flow(name="Start Volume Strategy", log_prints=True)
def start_volume_strategy_flow(
    symbol: str,
    quote_ccy: str = "USDT",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload = build_volume_strategy_payload(symbol, quote_ccy)
    response = call_ops_api_task(
        endpoint="/start_volume_strategy",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )
    logger = get_run_logger()
    logger.info(
        "Waiting %s seconds before checking volume strategy fills.",
        VOLUME_FILLS_DELAY_SECONDS,
    )
    time.sleep(VOLUME_FILLS_DELAY_SECONDS)
    call_ops_api_task(
        endpoint="/get_volume_strategy_fills",
        payload=build_volume_strategy_payload(symbol, quote_ccy),
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )
    return response


@flow(name="Stacker Status", log_prints=True)
def stacker_status_flow(
    symbol: str,
    date: str = "",
    quote_ccy: str = "USDT",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload = build_stacker_status_payload(symbol, quote_ccy)
    if date:
        payload["date"] = date
    return call_ops_api_task(
        endpoint="/get_stacker_accepted_orders",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )


@flow(name="Launch Stacker", log_prints=True)
def stacker_launch_flow(
    symbol: str,
    stacker_level: int = 1,
    quote_ccy: str = "USDT",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload = {
        "base_ccy": base_from_symbol(symbol, quote_ccy),
        "quote_ccy": quote_ccy.upper(),
        "stacker_level": stacker_level,
    }
    response = call_ops_api_task(
        endpoint="/launch_stacker",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )
    logger = get_run_logger()
    logger.info(
        "Waiting %s seconds before checking stacker status.",
        STACKER_STATUS_DELAY_SECONDS,
    )
    time.sleep(STACKER_STATUS_DELAY_SECONDS)
    call_ops_api_task(
        endpoint="/get_stacker_accepted_orders",
        payload=build_stacker_status_payload(symbol, quote_ccy),
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )
    return response


@flow(name="Setup Stacker Config", log_prints=True)
def stacker_setup_flow(
    symbol: str,
    feed_host: str,
    gateway_host: str,
    buy_stackers: str,
    sell_stackers: str,
    exchanges: str = "kucoin",
    quote_ccy: str = "USDT",
    market: Literal["spot", "perp"] = "spot",
    tick_size: float = 0.00001,
    quantity_step_size: float = 0.01,
    min_price: float = 0.00001,
    max_price: float = 5.0,
    min_quantity: float = 10.0,
    max_quantity: float = 100000000000,
    extra_payload_json: str = "{}",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload = {
        "exchanges": exchanges,
        "base_ccy": base_from_symbol(symbol, quote_ccy),
        "quote_ccy": quote_ccy.upper(),
        "market": market,
        "feed_host": feed_host,
        "gateway_host": gateway_host,
        "tick_size": tick_size,
        "quantity_step_size": quantity_step_size,
        "min_price": min_price,
        "max_price": max_price,
        "min_quantity": min_quantity,
        "max_quantity": max_quantity,
        "buy_stackers": buy_stackers,
        "sell_stackers": sell_stackers,
    }
    payload.update(parse_json_object(extra_payload_json, "extra_payload_json"))
    return call_ops_api_task(
        endpoint="/setup_stacker_config",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )


@flow(name="Update Stacker Config", log_prints=True)
def stacker_update_flow(
    symbol: str,
    updates_json: str,
    exchanges: str = "kucoin",
    quote_ccy: str = "USDT",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    payload = {
        "exchanges": exchanges,
        "base_ccy": base_from_symbol(symbol, quote_ccy),
        "quote_ccy": quote_ccy.upper(),
    }
    payload.update(parse_json_object(updates_json, "updates_json"))
    return call_ops_api_task(
        endpoint="/update_stacker_config",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )


def mirror_process_name(
    component: Literal["gateway", "feed", "strategy"],
    symbol: str,
    exchange: str,
    market: str,
    quote_ccy: str,
) -> str:
    compact_symbol = normalize_symbol(symbol, quote_ccy).replace("-", "")
    if component == "gateway":
        return f"mirror_{market}_gateway_custom_{compact_symbol}"
    if component == "feed":
        return f"feed_{market}_custom_{exchange}_{compact_symbol}"
    return f"mirror_{market}_listings_strat2_{compact_symbol}"


@flow(name="Mirror Process Control", log_prints=True)
def mirror_control_flow(
    symbol: str,
    component: Literal["gateway", "feed", "strategy"] = "strategy",
    method: Literal["start", "stop", "restart"] = "start",
    name_override: str = "",
    exchange: str = "kucoin",
    market: Literal["spot", "perp"] = "spot",
    quote_ccy: str = "USDT",
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
) -> dict[str, Any]:
    endpoint_by_component = {
        "gateway": "/gateway_control",
        "feed": "/feed_control",
        "strategy": "/strategy_control",
    }
    payload = {
        "method": method,
        "name": name_override
        or mirror_process_name(component, symbol, exchange, market, quote_ccy),
    }
    return call_ops_api_task(
        endpoint=endpoint_by_component[component],
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        send_signal_to_group=True,
    )
