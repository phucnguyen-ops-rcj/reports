from __future__ import annotations

import base64
from datetime import datetime
import json
import time
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request

import pandas as pd
from pydantic import BaseModel

from src.settings import app_settings


class OpenInterestSummary(BaseModel):
    base_asset: str
    date: datetime
    open_interest_usd: float
    previous_open_interest_usd: float | None

    @property
    def direction(self) -> str:
        if self.previous_open_interest_usd is None:
            return "flat"
        if self.open_interest_usd > self.previous_open_interest_usd:
            return "up"
        if self.open_interest_usd < self.previous_open_interest_usd:
            return "down"
        return "flat"

    @property
    def sentence(self) -> str:
        day = self.date.strftime("%-d %b")
        return (
            f"Overall {self.base_asset} OI was {self.direction} at "
            f"${self.open_interest_usd / 1_000_000_000:.1f}B on {day}, "
            "as compared to the previous day"
        )


class CoinankLongShortIntervalSnapshot(BaseModel):
    interval: str
    long_turnover: float | None
    short_turnover: float | None
    long_ratio: float | None
    short_ratio: float | None


class CoinankLongShortRealtimeSummary(BaseModel):
    base_asset: str
    price: float | None
    price_change_24h: float | None
    exchange_name: str | None
    symbol: str | None
    long_5m: CoinankLongShortIntervalSnapshot
    long_30m: CoinankLongShortIntervalSnapshot
    long_1h: CoinankLongShortIntervalSnapshot
    long_4h: CoinankLongShortIntervalSnapshot


class CoinankClient:
    _WEB_VERSION = "102"
    _PUBLIC_KEY = "b2d903dd-b31e-c547-d299-b6d07b7631ab"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_base_url: str | None = None,
        timeout: float = 10.0,
        api_key: str | None = None,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.coinank_base_url
        resolved_api_base_url = api_base_url or app_settings.coinank_api_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.api_base_url = resolved_api_base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.user_agent = user_agent

    def get_open_interest_chart(
        self,
        *,
        base_asset: str = "BTC",
        interval: str = "1d",
        open_type: str = "USD",
    ) -> pd.DataFrame:
        payload = self._get_api(
            "/api/openInterest/chart",
            params={
                "baseCoin": base_asset.upper(),
                "interval": interval,
                "type": open_type,
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise RuntimeError("CoinAnk returned an unexpected open-interest response.")

        timestamps = data.get("tss") or []
        prices = data.get("prices") or []
        data_values = data.get("dataValues") or {}
        if not isinstance(timestamps, list) or not isinstance(data_values, dict):
            raise RuntimeError("CoinAnk returned no open-interest chart data.")

        rows: list[dict[str, Any]] = []
        for index, timestamp_ms in enumerate(timestamps):
            open_interest = 0.0
            for exchange, values in data_values.items():
                if exchange == "Bitunix" or not isinstance(values, list):
                    continue
                if index < len(values) and values[index] is not None:
                    open_interest += float(values[index])

            price = prices[index] if index < len(prices) else None
            timestamp = pd.to_datetime(int(timestamp_ms), unit="ms")
            rows.append(
                {
                    "timestamp": timestamp,
                    "date": timestamp.normalize(),
                    "base_asset": base_asset.upper(),
                    "price": self._to_float(price),
                    "open_interest_usd": open_interest,
                }
            )

        return (
            pd.DataFrame(
                rows,
                columns=[
                    "timestamp",
                    "date",
                    "base_asset",
                    "price",
                    "open_interest_usd",
                ],
            )
            .drop_duplicates(subset=["date"], keep="first")
            .sort_values(by="date")
            .reset_index(drop=True)
        )

    def get_open_interest_summary(
        self,
        *,
        base_asset: str = "BTC",
        report_date: str | datetime | pd.Timestamp | None = None,
    ) -> OpenInterestSummary:
        df = self.get_open_interest_chart(base_asset=base_asset)
        if report_date is not None:
            df = df[df["date"] <= pd.Timestamp(report_date).normalize()]
        if len(df) < 1:
            raise RuntimeError(f"No {base_asset.upper()} open-interest data available.")

        latest = df.iloc[-1]
        previous = df.iloc[-2] if len(df) >= 2 else None
        return OpenInterestSummary(
            base_asset=base_asset.upper(),
            date=latest["date"].to_pydatetime(),
            open_interest_usd=float(latest["open_interest_usd"]),
            previous_open_interest_usd=(
                None if previous is None else float(previous["open_interest_usd"])
            ),
        )

    def get_long_short_realtime_summary(
        self,
        *,
        base_asset: str,
    ) -> CoinankLongShortRealtimeSummary:
        normalized_base_asset = base_asset.upper()
        market_info = self._get_base_coin_market_info(normalized_base_asset)
        snapshots = {
            interval: self._get_long_short_realtime_snapshot(
                base_asset=normalized_base_asset,
                interval=interval,
            )
            for interval in ("5m", "30m", "1h", "4h")
        }

        return CoinankLongShortRealtimeSummary(
            base_asset=normalized_base_asset,
            price=self._to_float(market_info.get("price")),
            price_change_24h=self._to_float(market_info.get("priceChange24h")),
            exchange_name=market_info.get("exchangeName"),
            symbol=market_info.get("symbol"),
            long_5m=snapshots["5m"],
            long_30m=snapshots["30m"],
            long_1h=snapshots["1h"],
            long_4h=snapshots["4h"],
        )

    def _get_long_short_realtime_snapshot(
        self,
        *,
        base_asset: str,
        interval: str,
    ) -> CoinankLongShortIntervalSnapshot:
        payload = self._get_api(
            "/api/longshort/realtimeAll",
            params={
                "interval": interval,
                "baseCoin": base_asset.upper(),
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise RuntimeError(
                "CoinAnk returned an unexpected long/short realtime response."
            )
        aggregate_row = next(
            (
                row
                for row in data
                if isinstance(row, dict) and row.get("exchangeName") == "All"
            ),
            None,
        )
        if not isinstance(aggregate_row, dict):
            raise RuntimeError(
                f"CoinAnk returned no aggregate long/short data for {base_asset.upper()} {interval}."
            )
        return CoinankLongShortIntervalSnapshot(
            interval=interval,
            long_turnover=self._to_float(aggregate_row.get("buyTradeTurnover")),
            short_turnover=self._to_float(aggregate_row.get("sellTradeTurnover")),
            long_ratio=self._to_float(aggregate_row.get("longRatio")),
            short_ratio=self._to_float(aggregate_row.get("shortRatio")),
        )

    def _get_base_coin_market_info(self, base_asset: str) -> dict[str, Any]:
        payload = self._get_api(
            "/api/instruments/base/searchPage",
            params={
                "baseCoin": base_asset.upper(),
                "size": "10",
                "page": "1",
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        items = data.get("list") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise RuntimeError(
                "CoinAnk returned an unexpected base-coin search response."
            )

        exact_match = next(
            (
                item
                for item in items
                if isinstance(item, dict)
                and str(item.get("baseCoin", "")).upper() == base_asset.upper()
            ),
            None,
        )
        if not isinstance(exact_match, dict):
            raise RuntimeError(
                f"CoinAnk returned no exact market row for {base_asset.upper()}."
            )
        return exact_match

    def _get_api(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        req = urllib.request.Request(
            url=f"{self.api_base_url}{endpoint}{query}",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"CoinAnk API HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"CoinAnk API request failed: {exc.reason}") from exc

        payload = json.loads(raw)
        if not payload.get("success"):
            raise RuntimeError(f"CoinAnk API error: {payload}")
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/openInterest/contract/BTC",
            "client": "web",
            "web-version": self._WEB_VERSION,
            "coinank-apikey": self.api_key or self._build_public_api_key(),
            "token": "",
        }
        return headers

    @classmethod
    def _build_public_api_key(cls) -> str:
        prefix = cls._PUBLIC_KEY[:8]
        rotated_key = cls._PUBLIC_KEY.replace(prefix, "") + prefix
        timestamp = f"{int(time.time() * 1000) + 2222222222222}347"
        return base64.b64encode(f"{rotated_key}|{timestamp}".encode()).decode()

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    from src.utils.visualization import coinank_open_interest_to_png

    client = CoinankClient()
    df = client.get_open_interest_chart(base_asset="BTC")

    summary = client.get_open_interest_summary(
        base_asset="BTC", report_date="2026-05-03"
    )
    print(summary.sentence)

    coinank_open_interest_to_png(
        df[df["date"] <= "2026-05-04"],
        "results/market/coinank_btc_open_interest.png",  # pyrefly: ignore
    )
    print(client.get_long_short_realtime_summary(base_asset="ALT"))
