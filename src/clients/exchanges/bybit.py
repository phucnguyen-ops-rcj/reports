from __future__ import annotations

import json
import pandas as pd
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request

from pydantic import BaseModel

from src.settings import app_settings


class BybitTicker24h(BaseModel):
    symbol: str
    base_asset: str
    last_price: float | None
    price_change_percent: float | None
    turnover_24h: float | None
    volume_24h: float | None


class BybitClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        api_key: str | None = None,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.bybit_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.user_agent = user_agent

    def get_linear_ticker(self, symbol: str) -> BybitTicker24h:
        payload = self._get(
            "/v5/market/tickers",
            params={"category": "linear", "symbol": symbol.upper()},
        )
        result = payload.get("result") if isinstance(payload, dict) else None
        items = result.get("list") if isinstance(result, dict) else None
        if not isinstance(items, list) or not items:
            raise RuntimeError(f"Bybit returned no ticker data for {symbol.upper()}.")
        item = items[0]
        if not isinstance(item, dict):
            raise RuntimeError("Bybit returned an unexpected ticker response shape.")
        return self._parse_ticker(item)

    def get_spot_ticker(self, symbol: str) -> BybitTicker24h:
        payload = self._get(
            "/v5/market/tickers",
            params={"category": "spot", "symbol": symbol.upper()},
        )
        result = payload.get("result") if isinstance(payload, dict) else None
        items = result.get("list") if isinstance(result, dict) else None
        if not isinstance(items, list) or not items:
            raise RuntimeError(
                f"Bybit returned no spot ticker data for {symbol.upper()}."
            )
        item = items[0]
        if not isinstance(item, dict):
            raise RuntimeError("Bybit returned an unexpected ticker response shape.")
        return self._parse_ticker(item)

    def get_usdt_perp_24h_turnover(self, base_asset: str) -> float | None:
        ticker = self.get_linear_ticker(f"{base_asset.upper()}USDT")
        return ticker.turnover_24h

    def get_spot_quote_volume_history(
        self,
        symbol: str,
        *,
        days: int,
        report_date: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")

        start_time_ms, end_time_ms = _daily_window_bounds_ms(report_date, days=days)
        payload = self._get(
            "/v5/market/kline",
            params={
                "category": "spot",
                "symbol": symbol.upper(),
                "interval": "D",
                "start": str(start_time_ms),
                "end": str(end_time_ms),
                "limit": str(days),
            },
        )
        result = payload.get("result") if isinstance(payload, dict) else None
        items = result.get("list") if isinstance(result, dict) else None
        if not isinstance(items, list):
            raise RuntimeError("Bybit returned an unexpected spot kline shape.")

        rows: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, list) or len(item) < 7:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(int(item[0]), unit="ms", utc=True)
                    .floor("D")
                    .tz_localize(None),
                    "quote_volume": self._to_float(item[6]),
                }
            )
        return pd.DataFrame(rows, columns=["date", "quote_volume"]).sort_values(
            by="date"
        )

    def get_spot_order_book(
        self,
        symbol: str,
        *,
        limit: int = 200,
    ) -> dict[str, Any]:
        payload = self._get(
            "/v5/market/orderbook",
            params={
                "category": "spot",
                "symbol": symbol.upper(),
                "limit": str(limit),
            },
        )
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise RuntimeError("Bybit returned an unexpected order-book shape.")
        return {
            "exchange": "bybit",
            "symbol": symbol.upper(),
            "bids": self._parse_price_levels(result.get("b")),
            "asks": self._parse_price_levels(result.get("a")),
            "timestamp_ms": self._to_int(result.get("ts")),
        }

    def _get(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        req = urllib.request.Request(
            url=f"{self.base_url}{endpoint}{query}",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Bybit API HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Bybit API request failed: {exc.reason}") from exc

        payload = json.loads(raw)
        if payload.get("retCode") != 0:
            raise RuntimeError(f"Bybit API error: {payload}")
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.api_key:
            headers["X-BAPI-API-KEY"] = self.api_key
        return headers

    @classmethod
    def _parse_ticker(cls, payload: dict[str, Any]) -> BybitTicker24h:
        symbol = str(payload.get("symbol", ""))
        return BybitTicker24h(
            symbol=symbol,
            base_asset=cls._base_asset(symbol),
            last_price=cls._to_float(payload.get("lastPrice")),
            price_change_percent=cls._to_percent(payload.get("price24hPcnt")),
            turnover_24h=cls._to_float(payload.get("turnover24h")),
            volume_24h=cls._to_float(payload.get("volume24h")),
        )

    @staticmethod
    def _base_asset(symbol: str, quote_asset: str = "USDT") -> str:
        if symbol.endswith(quote_asset):
            return symbol[: -len(quote_asset)]
        return symbol

    @staticmethod
    def _to_percent(value: Any) -> float | None:
        parsed = BybitClient._to_float(value)
        return None if parsed is None else parsed * 100

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _parse_price_levels(cls, payload: Any) -> list[tuple[float, float]]:
        if not isinstance(payload, list):
            return []

        levels: list[tuple[float, float]] = []
        for item in payload:
            if not isinstance(item, list) or len(item) < 2:
                continue
            price = cls._to_float(item[0])
            size = cls._to_float(item[1])
            if price is None or size is None:
                continue
            levels.append((price, size))
        return levels


def _daily_window_bounds_ms(
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
    return int(start_date.timestamp() * 1000), int(stop_date.timestamp() * 1000)
