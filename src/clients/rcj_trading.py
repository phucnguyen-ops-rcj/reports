from __future__ import annotations

import json
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request

from src.settings import app_settings


class RcjTradingAnalyzeType(StrEnum):
    SPOT = "Spot"
    PERP = "Future"


class RcjTradingAnalyzeVersion(StrEnum):
    NET = "Net"


class RcjTradingClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.rcj_trading_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    def get_analyze(
        self,
        *,
        symbols: list[str] | None = None,
        period_ms: int,
        analyze_type: RcjTradingAnalyzeType | str = RcjTradingAnalyzeType.SPOT,
        version: RcjTradingAnalyzeVersion | str = RcjTradingAnalyzeVersion.NET,
    ) -> Any:
        normalized_symbols = None
        if symbols is not None:
            normalized_symbols = [
                symbol.strip().upper() for symbol in symbols if symbol.strip()
            ]
            if not normalized_symbols:
                raise ValueError("symbols must contain at least one non-empty symbol.")
        if period_ms <= 0:
            raise ValueError("period_ms must be greater than zero.")

        request_type = (
            analyze_type.value
            if isinstance(analyze_type, RcjTradingAnalyzeType)
            else str(analyze_type)  # pyrefly: ignore
        )
        request_version = (
            version.value
            if isinstance(version, RcjTradingAnalyzeVersion)
            else str(version)  # pyrefly: ignore
        )

        return self._get(
            "/api/v1/analyze",
            params={
                **(
                    {"symbol": ",".join(normalized_symbols)}
                    if normalized_symbols is not None
                    else {}
                ),
                "period": str(period_ms),
                "type": request_type,
                "version": request_version,
            },
        )

    def _get(
        self,
        endpoint: str,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        query = f"?{urlencode(params)}" if params else ""
        request = urllib.request.Request(
            url=f"{self.base_url}{endpoint}{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"RCJ Trading HTTP {exc.code} from {self.base_url}{endpoint}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"RCJ Trading request failed for {self.base_url}{endpoint}: {exc.reason}"
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"RCJ Trading returned invalid JSON for {self.base_url}{endpoint}: {raw[:200]}"
            ) from exc


if __name__ == "__main__":
    client = RcjTradingClient()
    print(
        client.get_analyze(
            symbols=["PROVE"],
            analyze_type=RcjTradingAnalyzeType.PERP,
            period_ms=24 * 60 * 60 * 1000,
        )
    )
