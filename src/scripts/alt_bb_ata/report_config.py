from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "alt_report.json"


def load_alt_report_config(symbol: str) -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = payload.get(symbol.upper())
    if not isinstance(config, dict):
        raise ValueError(f"No ALT report configuration found for {symbol.upper()}.")
    return config


def load_alt_report_section(symbol: str, section: str) -> Any:
    config = load_alt_report_config(symbol)
    if section not in config:
        raise ValueError(f"No '{section}' configuration found for {symbol.upper()}.")
    return config[section]
