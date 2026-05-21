from __future__ import annotations

import json
import pandas as pd
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request


class GateioClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.gateio.ws/api/v4",
        timeout: float = 10.0,
        user_agent: str = "reports/1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    def get_spot_quote_volume_history(
        self,
        symbol: str,
        *,
        days: int,
        report_date: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")

        start_time_s, end_time_s = _daily_window_bounds_s(report_date, days=days)
        payload = self._get(
            "/spot/candlesticks",
            params={
                "currency_pair": symbol.upper(),
                "interval": "1d",
                "from": str(start_time_s),
                "to": str(end_time_s),
            },
        )
        if not isinstance(payload, list):
            raise RuntimeError("Gate.io returned an unexpected spot kline shape.")

        rows: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, list) or len(item) < 2:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(int(item[0]), unit="s", utc=True)
                    .floor("D")
                    .tz_localize(None),
                    "quote_volume": self._to_float(item[1]),
                }
            )
        return pd.DataFrame(rows, columns=["date", "quote_volume"]).sort_values(
            by="date"
        )

    def get_spot_order_book(
        self,
        symbol: str,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:
        payload = self._get(
            "/spot/order_book",
            params={"currency_pair": symbol.upper(), "limit": str(limit)},
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Gate.io returned an unexpected order-book shape.")
        return {
            "exchange": "gateio",
            "symbol": symbol.upper(),
            "bids": self._parse_price_levels(payload.get("bids")),
            "asks": self._parse_price_levels(payload.get("asks")),
            "timestamp_ms": None,
        }

    def _get(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        query = f"?{urlencode(params)}" if params else ""
        req = urllib.request.Request(
            url=f"{self.base_url}{endpoint}{query}",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gate.io API HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Gate.io API request failed: {exc.reason}") from exc

        return json.loads(raw)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _parse_price_levels(cls, payload: Any) -> list[tuple[float, float]]:
        if not isinstance(payload, list):
            return []

        levels: list[tuple[float, float]] = []
        for item in payload:
            if isinstance(item, list) and len(item) >= 2:
                price = cls._to_float(item[0])
                size = cls._to_float(item[1])
            elif isinstance(item, dict):
                price = cls._to_float(item.get("p") or item.get("price"))
                size = cls._to_float(item.get("s") or item.get("amount"))
            else:
                continue
            if price is None or size is None:
                continue
            levels.append((price, size))
        return levels


if __name__ == "__main__":
    client = GateioClient()
    print(client.get_spot_quote_volume_history("ALT_USDT", days=2))


def _daily_window_bounds_s(
    report_date: str | pd.Timestamp | None,
    *,
    days: int,
) -> tuple[int, int]:
    if report_date is None:
        end_date = pd.Timestamp.now(tz="UTC").normalize()
    else:
        end_date = pd.Timestamp(report_date)
        if end_date.tzinfo is None:
            end_date = end_date.tz_localize("UTC")
        else:
            end_date = end_date.tz_convert("UTC")
        end_date = end_date.normalize()

    start_date = end_date - pd.Timedelta(days=days - 1)
    stop_date = end_date + pd.Timedelta(days=1)
    return int(start_date.timestamp()), int(stop_date.timestamp())
