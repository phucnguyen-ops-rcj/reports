from __future__ import annotations

import json
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request

from pydantic import BaseModel
import pandas as pd

from src.settings import app_settings


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


class CoinMarketData(BaseModel):
    id: str
    symbol: str
    name: str
    base_asset: str
    last_price: float | None
    market_cap: float | None
    market_cap_rank: int | None
    total_volume: float | None
    price_change_percent: float | None


class CoinMarketChartPoint(BaseModel):
    timestamp_ms: int
    market_cap: float | None


class CoinSearchResult(BaseModel):
    id: str
    symbol: str
    name: str


class CoinGeckoClient:
    DEFAULT_HEATMAP_EXCLUDED_BASE_ASSETS = frozenset(
        {
            "BUSD",
            "DAI",
            "FDUSD",
            "FRAX",
            "GUSD",
            "LUSD",
            "PYUSD",
            "RLUSD",
            "TUSD",
            "USDC",
            "USDD",
            "USDE",
            "USDP",
            "USDS",
            "USDT",
            "USD1",
        }
    )

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        api_key: str | None = None,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.coingecko_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = (
            api_key if api_key is not None else app_settings.coingecko_api_key
        )
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
            total_market_cap_usd=self._nested_float(
                total_market_cap, QuoteCurrency.USD
            ),
            market_cap_change_percentage_24h_usd=self._to_float(
                data.get("market_cap_change_percentage_24h_usd")
            ),
            total_volume_usd=self._nested_float(total_volume, QuoteCurrency.USD),
            btc_dominance_percentage=self._nested_float(
                market_cap_percentage, QuoteCurrency.BTC
            ),
            eth_dominance_percentage=self._nested_float(
                market_cap_percentage, QuoteCurrency.ETH
            ),
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

    def get_coin_markets(
        self,
        *,
        vs_currency: QuoteCurrency | str = QuoteCurrency.USD,
        per_page: int = 50,
        page: int = 1,
        order: str = "market_cap_desc",
        price_change_percentage: str = "24h",
    ) -> list[CoinMarketData]:
        currency = (
            vs_currency.value if isinstance(vs_currency, QuoteCurrency) else vs_currency
        )
        payload = self._get(
            "/coins/markets",
            params={
                "vs_currency": currency,
                "order": order,
                "per_page": str(per_page),
                "page": str(page),
                "sparkline": "false",
                "price_change_percentage": price_change_percentage,
            },
        )
        if not isinstance(payload, list):
            raise RuntimeError("CoinGecko returned an unexpected coin markets shape.")
        return [
            self._parse_coin_market(item) for item in payload if isinstance(item, dict)
        ]

    def get_market_cap_heatmap_data(
        self,
        *,
        top_n: int = 50,
        vs_currency: QuoteCurrency | str = QuoteCurrency.USD,
        excluded_base_assets: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> pd.DataFrame:
        markets = self.get_coin_markets(
            vs_currency=vs_currency,
            per_page=min(max(top_n * 2, top_n), 250),
        )
        excluded = {
            asset.upper()
            for asset in (
                excluded_base_assets or self.DEFAULT_HEATMAP_EXCLUDED_BASE_ASSETS
            )
        }
        markets = [market for market in markets if market.base_asset not in excluded]
        return pd.DataFrame(
            [market.model_dump() for market in markets[:top_n]],
            columns=[
                "id",
                "symbol",
                "name",
                "base_asset",
                "last_price",
                "market_cap",
                "market_cap_rank",
                "total_volume",
                "price_change_percent",
            ],
        )

    def get_coin_market_chart(
        self,
        coin_id: str,
        *,
        days: int = 14,
        vs_currency: QuoteCurrency | str = QuoteCurrency.USD,
    ) -> pd.DataFrame:
        currency = (
            vs_currency.value if isinstance(vs_currency, QuoteCurrency) else vs_currency
        )
        payload = self._get(
            f"/coins/{coin_id}/market_chart",
            params={
                "vs_currency": currency,
                "days": str(days),
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError(
                "CoinGecko returned an unexpected coin chart response shape."
            )

        market_caps = payload.get("market_caps")
        if not isinstance(market_caps, list):
            raise RuntimeError("CoinGecko returned no market cap chart data.")

        points = [
            CoinMarketChartPoint(
                timestamp_ms=int(item[0]),
                market_cap=self._to_float(item[1]),
            )
            for item in market_caps
            if isinstance(item, list) and len(item) >= 2
        ]
        return pd.DataFrame(
            [point.model_dump() for point in points],
            columns=["timestamp_ms", "market_cap"],
        )

    def get_global_market_cap_chart(
        self,
        *,
        days: int = 14,
        vs_currency: QuoteCurrency | str = QuoteCurrency.USD,
    ) -> pd.DataFrame:
        currency = (
            vs_currency.value if isinstance(vs_currency, QuoteCurrency) else vs_currency
        )
        payload = self._get(
            "/global/market_cap_chart",
            params={
                "days": str(days),
                "vs_currency": currency,
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError(
                "CoinGecko returned an unexpected global chart response shape."
            )

        chart = payload.get("market_cap_chart")
        if not isinstance(chart, dict):
            raise RuntimeError("CoinGecko returned no global market cap chart data.")

        market_caps = chart.get("market_cap")
        if not isinstance(market_caps, list):
            raise RuntimeError("CoinGecko returned no global market cap series.")

        points = [
            CoinMarketChartPoint(
                timestamp_ms=int(item[0]),
                market_cap=self._to_float(item[1]),
            )
            for item in market_caps
            if isinstance(item, list) and len(item) >= 2
        ]
        return pd.DataFrame(
            [point.model_dump() for point in points],
            columns=["timestamp_ms", "market_cap"],
        )

    def get_coin_price_chart(
        self,
        coin_id: str,
        *,
        days: int = 14,
        vs_currency: QuoteCurrency | str = QuoteCurrency.USD,
    ) -> pd.DataFrame:
        currency = (
            vs_currency.value if isinstance(vs_currency, QuoteCurrency) else vs_currency
        )
        payload = self._get(
            f"/coins/{coin_id}/market_chart",
            params={
                "vs_currency": currency,
                "days": str(days),
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError(
                "CoinGecko returned an unexpected coin chart response shape."
            )

        prices = payload.get("prices")
        if not isinstance(prices, list):
            raise RuntimeError("CoinGecko returned no price chart data.")

        rows = [
            {"timestamp_ms": int(item[0]), "price": self._to_float(item[1])}
            for item in prices
            if isinstance(item, list) and len(item) >= 2
        ]
        return pd.DataFrame(rows, columns=["timestamp_ms", "price"])

    def search_coins(self, query: str) -> list[CoinSearchResult]:
        payload = self._get("/search", params={"query": query})
        if not isinstance(payload, dict):
            raise RuntimeError(
                "CoinGecko returned an unexpected search response shape."
            )

        coins = payload.get("coins")
        if not isinstance(coins, list):
            return []
        results: list[CoinSearchResult] = []
        for item in coins:
            if not isinstance(item, dict):
                continue
            result = CoinSearchResult(
                id=str(item.get("id", "")),
                symbol=str(item.get("symbol", "")),
                name=str(item.get("name", "")),
            )
            if result.id:
                results.append(result)
        return results

    def resolve_coin_id(
        self,
        query: str,
        *,
        preferred_ids: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> str | None:
        preferred = {item.lower() for item in (preferred_ids or []) if item}
        if preferred:
            results = self.search_coins(query)
            for result in results:
                if result.id.lower() in preferred:
                    return result.id

        results = self.search_coins(query)
        normalized_query = query.strip().lower()
        for result in results:
            if result.symbol.strip().lower() == normalized_query:
                return result.id
        for result in results:
            if result.name.strip().lower() == normalized_query:
                return result.id
        return results[0].id if results else None

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
            if "pro-api" in self.base_url:
                headers["x-cg-pro-api-key"] = self.api_key
            else:
                headers["x-cg-demo-api-key"] = self.api_key
        return headers

    @classmethod
    def _parse_coin_market(cls, payload: dict[str, Any]) -> CoinMarketData:
        symbol = str(payload.get("symbol", "")).upper()
        return CoinMarketData(
            id=str(payload.get("id", "")),
            symbol=symbol,
            name=str(payload.get("name", "")),
            base_asset=symbol,
            last_price=cls._to_float(payload.get("current_price")),
            market_cap=cls._to_float(payload.get("market_cap")),
            market_cap_rank=cls._to_int(payload.get("market_cap_rank")),
            total_volume=cls._to_float(payload.get("total_volume")),
            price_change_percent=cls._to_float(
                payload.get("price_change_percentage_24h")
            ),
        )

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
