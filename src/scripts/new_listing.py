from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.settings import app_settings

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("src/config/new_listing/template.json")
DEFAULT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class ApiResponse:
    step: str
    status: int
    body: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the new-listing setup sequence from a copied JSON payload file."
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Path to a JSON file copied from src/config/new_listing/template.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the step order and JSON bodies without sending requests.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError("New listing config must be a JSON object.")
    if "steps" not in config or not isinstance(config["steps"], dict):
        raise ValueError("New listing config must contain a 'steps' object.")

    return config


def require_token() -> str:
    token = app_settings.rcj_ops_bearer_token.strip()
    if not token:
        raise RuntimeError("RCJ_OPS_BEARER_TOKEN is not set.")
    return token


def get_step_config(config: dict[str, Any], step: str) -> dict[str, Any]:
    steps = config["steps"]
    if step not in steps:
        raise ValueError(f"Missing step {step} in config.")

    step_config = steps[step]
    if not isinstance(step_config, dict):
        raise ValueError(f"Step {step} must be a JSON object.")
    if not isinstance(step_config.get("label"), str):
        raise ValueError(f"Step {step} must define a string label.")
    if not isinstance(step_config.get("endpoint"), str):
        raise ValueError(f"Step {step} must define a string endpoint.")
    if not isinstance(step_config.get("body"), dict):
        raise ValueError(f"Step {step} must define a JSON object body.")
    return step_config


def get_step_body(config: dict[str, Any], step: str) -> dict[str, Any]:
    return get_step_config(config, step)["body"]


def post_json(
    base_url: str,
    endpoint: str,
    token: str,
    payload: dict[str, Any],
    timeout: int,
) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{endpoint}",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


def utc_midnight_timestamp_ms() -> int:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * 1000)


def create_run_log_path(config: dict[str, Any]) -> Path:
    symbol = symbol_from_config(config) or "unknown"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    logs_dir = Path(config.get("logs_dir", "logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / f"{symbol}_{timestamp}.log"


def write_step_log(
    log_path: Path,
    step: str,
    step_config: dict[str, Any],
    response: ApiResponse,
    dry_run: bool,
) -> None:
    with log_path.open("a", encoding="utf-8") as file:
        file.write(
            f"[{datetime.now(timezone.utc).isoformat()}] Step {step}: {step_config['label']}\n"
        )
        file.write(f"Endpoint: {step_config['endpoint']}\n")
        file.write(f"Dry run: {dry_run}\n")
        file.write("Input:\n")
        file.write(json.dumps(step_config["body"], indent=2, sort_keys=True))
        file.write("\n")
        file.write(f"Status: {response.status}\n")
        file.write("Output:\n")
        file.write(response.body.rstrip())
        file.write("\n")
        file.write("=" * 80)
        file.write("\n")


def write_skip_log(
    log_path: Path, step: str, config: dict[str, Any], reason: str
) -> None:
    step_config = get_step_config(config, step)
    response = ApiResponse(step=step, status=0, body=f"skipped: {reason}")
    write_step_log(log_path, step, step_config, response, dry_run=False)


def run_step(
    step: str,
    config: dict[str, Any],
    token: str,
    dry_run: bool,
    log_path: Path,
) -> ApiResponse:
    step_config = get_step_config(config, step)
    label = step_config["label"]
    endpoint = step_config["endpoint"]
    payload = step_config["body"]

    logger.info("Running step %s: %s", step, label)
    if dry_run:
        print(f"\nStep {step} - {label}")
        print(json.dumps(payload, indent=2, sort_keys=True))
        response = ApiResponse(step=step, status=200, body="dry-run")
        write_step_log(log_path, step, step_config, response, dry_run=True)
        return response

    status, body = post_json(
        base_url=str(config.get("base_endpoint", "http://18.176.93.228")),
        endpoint=endpoint,
        token=token,
        payload=payload,
        timeout=int(config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
    )
    response = ApiResponse(step=step, status=status, body=body)
    logger.info("Step %s finished with HTTP %s", step, status)
    print_response(response)
    write_step_log(log_path, step, step_config, response, dry_run=False)
    if not response.ok:
        raise RuntimeError(f"Step {step} failed with HTTP {status}.")
    return response


def print_response(response: ApiResponse) -> None:
    print(f"\nStep {response.step} HTTP {response.status}")
    print(response.body.rstrip())


def response_has_symbol_not_found(response: ApiResponse) -> bool:
    return "symbol not found" in response.body.lower()


def feed_was_created(response: ApiResponse) -> bool:
    return extract_feed_action(response.body) != "appended symbol to existing feed"


def extract_feed_action(body: str) -> str | None:
    parsed = parse_json_response(body)
    if isinstance(parsed, dict):
        action = parsed.get("feed_action")
        if isinstance(action, str) and action:
            return action.lower()

    match = re.search(r"\bfeed_action\s*:\s*([^\n\r]+)", body, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().lower()
    return None


def parse_json_response(body: str) -> Any | None:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def symbol_from_config(config: dict[str, Any]) -> str | None:
    step6 = get_step_body(config, "6")
    step2 = get_step_body(config, "2")
    base_ccy = step6.get("base_ccy") or step2.get("base_ccy")
    if isinstance(base_ccy, str) and base_ccy:
        return base_ccy.upper()

    symbol = get_step_body(config, "3").get("symbol")
    if isinstance(symbol, str) and symbol:
        return symbol.split("-")[0].upper()
    return None


def gateway_host_from_config(config: dict[str, Any]) -> str | None:
    host = get_step_body(config, "6").get("gateway_host")
    return host if isinstance(host, str) and host else None


def extract_feed_config(body: str) -> str | None:
    match = re.search(
        r"\[feed config]\s*(.*?)(?:\n=+\n|\n\[strategy config]|\Z)",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return None
    feed_config = match.group(1).strip()
    return feed_config or None


def load_gateway_feed_configs(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    configs: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key_match = re.fullmatch(r'"([^"]+)":\s*\|', stripped)
        if key_match:
            if current_key:
                configs[current_key] = "\n".join(current_lines).rstrip()
            current_key = key_match.group(1)
            current_lines = []
            continue

        if current_key and line.startswith("  "):
            current_lines.append(line[2:])

    if current_key:
        configs[current_key] = "\n".join(current_lines).rstrip()
    return configs


def save_gateway_feed_configs(path: Path, configs: dict[str, str]) -> None:
    lines = [
        "# Gateway host to latest feed config returned by Step 6.",
        "# Keep this in sync after each successful new-listing run.",
    ]
    for host in sorted(configs):
        lines.append(f'"{host}": |')
        for config_line in configs[host].splitlines():
            lines.append(f"  {config_line}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_gateway_symbols(config: dict[str, Any], step6_body: str) -> None:
    if config.get("update_gateway_symbols", True) is False:
        return

    path = Path(
        config.get("gateway_symbols_path", "src/config/new_listing/gateway_symbols.yml")
    )
    gateway_host = gateway_host_from_config(config)
    feed_config = extract_feed_config(step6_body)
    if not gateway_host or not feed_config:
        logger.warning(
            "Skipping gateway symbol update because gateway_host or feed config is missing."
        )
        return

    configs = load_gateway_feed_configs(path)
    configs[gateway_host] = feed_config
    save_gateway_feed_configs(path, configs)
    logger.info("Updated %s with latest Step 6 feed config for %s", path, gateway_host)


def run_new_listing(config: dict[str, Any], dry_run: bool = False) -> None:
    log_path = create_run_log_path(config)
    logger.info("Writing new-listing run log to %s", log_path)
    token = "" if dry_run else require_token()
    create_gateway = bool(
        config.get("create_new_gate_way", config.get("create_new_gateway", False))
    )

    run_step("1", config, token, dry_run, log_path)
    run_step("2", config, token, dry_run, log_path)

    step3 = run_step("3", config, token, dry_run, log_path)
    if not dry_run and response_has_symbol_not_found(step3):
        logger.info(
            "Step 3 returned symbol-not-found; running Step 3b and retrying Step 3."
        )
        get_step_body(config, "3b")["first_date"] = utc_midnight_timestamp_ms()
        run_step("3b", config, token, dry_run, log_path)
        # run_step("3", config, token, dry_run, log_path)

    if create_gateway:
        run_step("4", config, token, dry_run, log_path)
        run_step("5", config, token, dry_run, log_path)
    else:
        logger.info("Skipping steps 4 and 5 because create_new_gate_way is false.")
        write_skip_log(log_path, "4", config, "create_new_gate_way is false")
        write_skip_log(log_path, "5", config, "create_new_gate_way is false")

    step6 = run_step("6", config, token, dry_run, log_path)

    if dry_run or feed_was_created(step6):
        run_step("7", config, token, dry_run, log_path)
    else:
        logger.info("Skipping step 7 because Step 6 did not create a new feed file.")
        action = extract_feed_action(step6.body) or "missing feed_action"
        write_skip_log(log_path, "7", config, f"Step 6 feed_action is {action}")

    run_step("8", config, token, dry_run, log_path)
    if not dry_run:
        update_gateway_symbols(config, step6.body)


def main() -> None:
    logging.basicConfig(
        level=app_settings.log_level.upper(),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    args = parse_args()
    config = load_config(Path(args.config))
    run_new_listing(config, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("New listing setup failed: %s", exc, exc_info=True)
        sys.exit(1)
