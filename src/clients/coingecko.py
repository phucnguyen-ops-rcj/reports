from __future__ import annotations

import json
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request

from pydantic import BaseModel

from src.settings import get_settings


class QuoteCurrency(StrEnum):
    USD = "usd"
    BTC = "btc"
    ETH = "eth"


class GlobalMarketSummary(BaseModel):
    active_cryptocurrencies: int | None
    markets: int | None
    total_market_cap_usd: float | None
    market_cap_change_percentage_24h_usd: float | None
    total_volume_usd: float | None
    btc_dominance_percentage: float | None
    eth_dominance_percentage: float | None
    volume_change_percentage_24h_usd: float | None
    updated_at: int | None


class CoinGeckoClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        api_key: str | None = None,
        user_agent: str = "reports/1.0",
    ) -> None:
        app_settings = get_settings()
        resolved_base_url = base_url or app_settings.coingecko_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key if api_key is not None else app_settings.coingecko_api_key
        self.user_agent = user_agent

    def get_global_market_summary(self) -> GlobalMarketSummary:
        payload = self._get("/global")
        if not isinstance(payload, dict):
            raise RuntimeError("CoinGecko returned an unexpected response shape.")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("CoinGecko returned no global market data.")

        total_market_cap = data.get("total_market_cap")
        market_cap_percentage = data.get("market_cap_percentage")
        total_volume = data.get("total_volume")

        return GlobalMarketSummary(
            active_cryptocurrencies=self._to_int(data.get("active_cryptocurrencies")),
            markets=self._to_int(data.get("markets")),
            total_market_cap_usd=self._nested_float(total_market_cap, QuoteCurrency.USD),
            market_cap_change_percentage_24h_usd=self._to_float(
                data.get("market_cap_change_percentage_24h_usd")
            ),
            total_volume_usd=self._nested_float(total_volume, QuoteCurrency.USD),
            btc_dominance_percentage=self._nested_float(market_cap_percentage, QuoteCurrency.BTC),
            eth_dominance_percentage=self._nested_float(market_cap_percentage, QuoteCurrency.ETH),
            volume_change_percentage_24h_usd=self._to_float(
                data.get("volume_change_percentage_24h_usd")
            ),
            updated_at=self._to_int(data.get("updated_at")),
        )

    def get_active_cryptocurrencies_count(self) -> int | None:
        return self.get_global_market_summary().active_cryptocurrencies

    def get_markets_count(self) -> int | None:
        return self.get_global_market_summary().markets

    def get_total_market_cap_usd(self) -> float | None:
        return self.get_global_market_summary().total_market_cap_usd

    def get_market_cap_change_percentage_24h_usd(self) -> float | None:
        return self.get_global_market_summary().market_cap_change_percentage_24h_usd

    def get_total_volume_usd(self) -> float | None:
        return self.get_global_market_summary().total_volume_usd

    def get_btc_dominance_percentage(self) -> float | None:
        return self.get_global_market_summary().btc_dominance_percentage

    def get_eth_dominance_percentage(self) -> float | None:
        return self.get_global_market_summary().eth_dominance_percentage

    def _get(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
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
            raise RuntimeError(f"CoinGecko API HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"CoinGecko API request failed: {exc.reason}") from exc

        return json.loads(raw)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.api_key:
            headers["x-cg-demo-api-key"] = self.api_key
        return headers

    @staticmethod
    def _nested_float(value: Any, key: QuoteCurrency | str) -> float | None:
        if not isinstance(value, dict):
            return None
        lookup_key = key.value if isinstance(key, QuoteCurrency) else key
        return CoinGeckoClient._to_float(value.get(lookup_key))

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


if __name__ == "__main__":
    client = CoinGeckoClient()
    summary = client.get_global_market_summary()
    print(summary)
