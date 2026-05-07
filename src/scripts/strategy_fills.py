from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import Any

from src.clients.ops_api import (
    DEFAULT_OPS_BASE_ENDPOINT,
    DEFAULT_OPS_EXECUTION_MODE,
    DEFAULT_OPS_SSH_HOST,
    DEFAULT_OPS_TIMEOUT_SECONDS,
    OpsApiClient,
    normalize_symbol,
)
from src.settings import app_settings

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch strategy fill/status data from the RCJ ops API."
    )
    parser.add_argument(
        "symbol",
        help="Base or trade symbol. Example: KAIO or KAIO-USDT.",
    )
    parser.add_argument(
        "--date",
        help="Optional YYYYMMDD date for endpoints that support date filters.",
    )
    parser.add_argument(
        "--endpoint",
        default="/get_volume_strategy_fills",
        help="Ops API endpoint path. Defaults to /get_volume_strategy_fills.",
    )
    parser.add_argument(
        "--base-endpoint",
        default=DEFAULT_OPS_BASE_ENDPOINT,
        help=f"Ops API base endpoint. Defaults to {DEFAULT_OPS_BASE_ENDPOINT}.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_OPS_TIMEOUT_SECONDS,
        help=f"Request timeout in seconds. Defaults to {DEFAULT_OPS_TIMEOUT_SECONDS}.",
    )
    parser.add_argument(
        "--execution-mode",
        choices=["ssh", "local"],
        default=DEFAULT_OPS_EXECUTION_MODE,
        help="Run API requests through SSH by default, or directly from local.",
    )
    parser.add_argument(
        "--ssh-host",
        default=DEFAULT_OPS_SSH_HOST,
        help=f"SSH host used when --execution-mode=ssh. Defaults to {DEFAULT_OPS_SSH_HOST}.",
    )
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    symbol = normalize_symbol(args.symbol)
    base_currency, quote_currency = symbol.split("-", maxsplit=1)
    payload: dict[str, Any] = {
        "base_currency": base_currency,
        "quote_currency": quote_currency,
    }
    if args.date:
        datetime.strptime(args.date, "%Y%m%d")
        payload["date"] = args.date
    return payload


def main() -> None:
    logging.basicConfig(
        level=app_settings.log_level.upper(),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    args = parse_args()
    payload = build_payload(args)
    client = OpsApiClient(
        base_endpoint=args.base_endpoint,
        timeout_seconds=args.timeout,
        execution_mode=args.execution_mode,
        ssh_host=args.ssh_host,
    )
    response = client.post(args.endpoint, payload)
    print(f"HTTP {response.status}")
    print(response.body.rstrip())
    if not response.ok:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("Strategy fills request failed: %s", exc, exc_info=True)
        sys.exit(1)
