from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request


class SignalClient:
    def __init__(self, sender: str = "+84559854979", base_url: str = "http://127.0.0.1:8080") -> None:
        self.sender = sender
        self.base_url = base_url.rstrip("/")

    def send(
        self,
        message: str | Path | list[str | Path] | tuple[str | Path, ...],
        *,
        recipient: str | None = None,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        recipients = self._resolve_recipients(recipient=recipient, group_id=group_id)
        text, attachments = self._normalize_message(message)

        payload: dict[str, Any] = {
            "message": text,
            "number": self.sender,
            "recipients": recipients,
        }
        if attachments:
            payload["base64_attachments"] = attachments

        return self._post("/v2/send", payload)

    def _resolve_recipients(
        self,
        *,
        recipient: str | None,
        group_id: str | None,
    ) -> list[str]:
        if bool(recipient) == bool(group_id):
            raise ValueError("Pass exactly one of recipient or group_id.")
        return [recipient] if recipient else [group_id]  # type: ignore[list-item]

    def _normalize_message(
        self,
        message: str | Path | list[str | Path] | tuple[str | Path, ...],
    ) -> tuple[str, list[str]]:
        if isinstance(message, Path):
            return "", [self._encode_file(message)]

        if isinstance(message, str):
            path = Path(message)
            if path.exists() and path.is_file():
                return "", [self._encode_file(path)]
            return message, []

        if isinstance(message, (list, tuple)):
            if not message:
                raise ValueError("message list cannot be empty.")
            attachments = [self._encode_file(Path(item)) for item in message]
            return "", attachments

        raise TypeError("message must be text, a file path, or a list of file paths.")

    def _encode_file(self, file_path: Path) -> str:
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Attachment not found: {file_path}")
        return base64.b64encode(file_path.read_bytes()).decode("utf-8")

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.base_url}{endpoint}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Signal API HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Signal API request failed: {exc.reason}") from exc

        if not raw:
            return {"success": True}
        return json.loads(raw)
