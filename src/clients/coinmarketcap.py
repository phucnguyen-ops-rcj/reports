from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request

from pydantic import BaseModel

from src.settings import app_settings


class CoinMarketCapQuote(BaseModel):
    symbol: str
    name: str | None
    slug: str | None
    price: float | None
    volume_24h: float | None
    market_cap: float | None
    percent_change_24h: float | None


class CoinMarketCapClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        api_key: str | None = None,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.coinmarketcap_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = (
            api_key if api_key is not None else app_settings.coinmarketcap_api_key
        )
        self.user_agent = user_agent

    def get_quote(
        self,
        symbol: str | None = None,
        *,
        slug: str | None = None,
        convert: str = "USD",
    ) -> CoinMarketCapQuote:
        if bool(symbol) == bool(slug):
            raise ValueError("Pass exactly one of symbol or slug.")
        params = {"convert": convert.upper()}
        if slug:
            params["slug"] = slug.lower()
        else:
            assert symbol is not None
            params["symbol"] = symbol.upper()

        payload = self._get(
            "/v3/cryptocurrency/quotes/latest",
            params=params,
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            records = data.get(symbol.upper()) if symbol else None
            if isinstance(records, list) and records:
                return self._parse_quote(records[0], convert=convert)
            if isinstance(records, dict):
                return self._parse_quote(records, convert=convert)
        if isinstance(data, list) and data:
            return self._parse_quote(data[0], convert=convert)
        lookup = slug or symbol
        raise RuntimeError(f"CoinMarketCap returned no quote data for {lookup}.")

    def get_spot_volume_24h(
        self,
        symbol: str | None = None,
        *,
        slug: str | None = None,
        convert: str = "USD",
    ) -> float | None:
        return self.get_quote(symbol, slug=slug, convert=convert).volume_24h

    def _get(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("CoinMarketCap API key is required.")
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
            raise RuntimeError(
                f"CoinMarketCap API HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"CoinMarketCap API request failed: {exc.reason}"
            ) from exc

        payload = json.loads(raw)
        status = payload.get("status") if isinstance(payload, dict) else None
        if isinstance(status, dict) and str(status.get("error_code", "0")) != "0":
            raise RuntimeError(f"CoinMarketCap API error: {status}")
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "X-CMC_PRO_API_KEY": self.api_key,
        }

    @classmethod
    def _parse_quote(
        cls,
        payload: dict[str, Any],
        *,
        convert: str,
    ) -> CoinMarketCapQuote:
        quote = payload.get("quote")
        quote_data = quote.get(convert.upper()) if isinstance(quote, dict) else {}
        if isinstance(quote, list):
            quote_data = next(
                (
                    item
                    for item in quote
                    if isinstance(item, dict)
                    and str(item.get("symbol", "")).upper() == convert.upper()
                ),
                {},
            )
        quote_data = quote_data if isinstance(quote_data, dict) else {}
        return CoinMarketCapQuote(
            symbol=str(payload.get("symbol", "")),
            name=payload.get("name"),
            slug=payload.get("slug"),
            price=cls._to_float(quote_data.get("price")),
            volume_24h=cls._to_float(quote_data.get("volume_24h")),
            market_cap=cls._to_float(quote_data.get("market_cap")),
            percent_change_24h=cls._to_float(quote_data.get("percent_change_24h")),
        )

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    client = CoinMarketCapClient()
    print(client.get_spot_volume_24h(slug="altlayer"))
