from __future__ import annotations

import json
import re
from typing import Any

_SSH_MOTD_PATTERNS = (
    re.compile(r"^Welcome to Ubuntu\b"),
    re.compile(r"^\s*\*\s+Documentation:"),
    re.compile(r"^\s*\*\s+Management:"),
    re.compile(r"^\s*\*\s+Support:"),
    re.compile(r"^\s*System information as of\b"),
    re.compile(r"^\s*System load:"),
    re.compile(r"^\s*Usage of /:"),
    re.compile(r"^\s*Memory usage:"),
    re.compile(r"^\s*Swap usage:"),
    re.compile(r"^\s*Processes:"),
    re.compile(r"^\s*Users logged in:"),
    re.compile(r"^\s*IPv4 address for\b"),
    re.compile(r"^\s*=> / is using\b"),
    re.compile(r"^\s*\*\s+Ubuntu Pro delivers\b"),
    re.compile(r"^\s*Expanded Security Maintenance\b"),
    re.compile(r"^\s*\d+\s+updates can be applied immediately\.$"),
    re.compile(r"^\s*To see these additional updates run:"),
    re.compile(r"^\s*\d+\s+additional security updates can be applied\b"),
    re.compile(r"^\s*Learn more about enabling ESM Apps service\b"),
    re.compile(r"^New release '.+' available\.$"),
    re.compile(r"^Run 'do-release-upgrade' to upgrade to it\.$"),
    re.compile(r"^\*\*\* System restart required \*\*\*$"),
    re.compile(r"^https?://"),
)

_SSH_MOTD_END_MARKERS = (
    "*** System restart required ***",
    "Run 'do-release-upgrade' to upgrade to it.",
    "Learn more about enabling ESM Apps service at https://ubuntu.com/esm",
)


def format_ops_response_body(endpoint: str, body: str) -> str:
    payload = extract_json_payload(body)
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, indent=2, ensure_ascii=False)

    cleaned_body = strip_ssh_motd(body).rstrip()
    if endpoint == "/get_stacker_accepted_orders":
        return format_stacker_status_response(cleaned_body)
    return cleaned_body or "<empty response>"


def format_stacker_status_response(body: str) -> str:
    blocks: list[str] = []
    header: str | None = None
    counts = {
        "NEW_ORDER_STATUS_ACCEPTED": 0,
        "NEW_ORDER_STATUS_REJECTED": 0,
    }

    def flush_block() -> None:
        if header is None:
            return
        blocks.append(
            "\n".join(
                [
                    header,
                    f"NEW_ORDER_STATUS_ACCEPTED = {counts['NEW_ORDER_STATUS_ACCEPTED']}",
                    f"NEW_ORDER_STATUS_REJECTED = {counts['NEW_ORDER_STATUS_REJECTED']}",
                ]
            )
        )

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("=") or line == "✅ success":
            continue
        if line.endswith(".txtpb.INFO:"):
            flush_block()
            header = line
            counts = {
                "NEW_ORDER_STATUS_ACCEPTED": 0,
                "NEW_ORDER_STATUS_REJECTED": 0,
            }
            continue

        match = re.fullmatch(
            r"(NEW_ORDER_STATUS_(?:ACCEPTED|REJECTED))\s*=\s*(\d+)",
            line,
        )
        if match and header is not None:
            counts[match.group(1)] = int(match.group(2))

    flush_block()
    return "\n".join(blocks) or body or "<empty response>"


def extract_json_payload(body: str) -> dict[str, Any] | list[Any] | None:
    decoder = json.JSONDecoder()
    latest_payload: dict[str, Any] | list[Any] | None = None
    latest_payload_span = -1
    for index, char in enumerate(body):
        if char not in "[{":
            continue
        try:
            payload, end_index = decoder.raw_decode(body[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, (dict, list)) and end_index > latest_payload_span:
            latest_payload = payload
            latest_payload_span = end_index
    return latest_payload


def strip_ssh_motd(body: str) -> str:
    for marker in _SSH_MOTD_END_MARKERS:
        if marker in body:
            _, remainder = body.rsplit(marker, maxsplit=1)
            stripped = remainder.lstrip("\n")
            if stripped:
                return stripped

    lines = body.splitlines()
    if not lines:
        return body

    index = 0
    saw_motd = False
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            if saw_motd:
                index += 1
                continue
            break
        if any(pattern.search(stripped) for pattern in _SSH_MOTD_PATTERNS):
            saw_motd = True
            index += 1
            continue
        break

    if not saw_motd:
        return body
    return "\n".join(lines[index:])
