from __future__ import annotations

import json
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
from src.scripts.new_listing import load_config, resolve_config_path, run_new_listing


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
    base_endpoint: str = DEFAULT_OPS_BASE_ENDPOINT,
    timeout_seconds: int = DEFAULT_OPS_TIMEOUT_SECONDS,
    execution_mode: Literal["ssh", "local"] = DEFAULT_OPS_EXECUTION_MODE,
    ssh_host: str = DEFAULT_OPS_SSH_HOST,
    fail_on_error: bool = True,
) -> dict[str, Any]:
    logger = get_run_logger()
    logger.info("POST %s", endpoint)
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
    response = client.post(endpoint, payload)
    logger.info("HTTP %s", response.status)
    logger.info("Response:\n%s", response.body.rstrip())
    print(f"HTTP {response.status}")
    print(response.body.rstrip())

    if fail_on_error and not response.ok:
        raise RuntimeError(f"{endpoint} failed with HTTP {response.status}.")
    return response.as_dict()


@flow(name="Ops API Request", log_prints=True)
def ops_api_request_flow(
    endpoint: str,
    payload_json: str = "{}",
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
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
        fail_on_error=fail_on_error,
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
    resolved_path = resolve_config_path(args)
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
    payload: dict[str, Any] = {
        "base_currency": base_from_symbol(symbol, quote_ccy),
        "quote_currency": quote_ccy.upper(),
    }
    if date:
        payload["date"] = date
    return call_ops_api_task(
        endpoint="/get_volume_strategy_fills",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
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
    payload = {
        "base_currency": base_from_symbol(symbol, quote_ccy),
        "quote_currency": quote_ccy.upper(),
    }
    return call_ops_api_task(
        endpoint="/start_volume_strategy",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
    )


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
    payload: dict[str, Any] = {"symbol": normalize_symbol(symbol, quote_ccy)}
    if date:
        payload["date"] = date
    return call_ops_api_task(
        endpoint="/get_stacker_accepted_orders",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
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
    return call_ops_api_task(
        endpoint="/launch_stacker",
        payload=payload,
        base_endpoint=base_endpoint,
        timeout_seconds=timeout_seconds,
        execution_mode=execution_mode,
        ssh_host=ssh_host,
    )


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
    )
