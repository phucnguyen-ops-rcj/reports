from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request

import pandas as pd
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


class CoinMarketCapLiquidationsSummary(BaseModel):
    total: float | None
    longs: float | None
    shorts: float | None


class CoinMarketCapClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        public_data_api_base_url: str = "https://api.coinmarketcap.com",
        liquidations_page_url: str = "https://coinmarketcap.com/charts/liquidations/",
        timeout: float = 10.0,
        api_key: str | None = None,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.coinmarketcap_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.public_data_api_base_url = public_data_api_base_url.rstrip("/")
        self.liquidations_page_url = liquidations_page_url
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

    def get_liquidations_summary(self) -> CoinMarketCapLiquidationsSummary:
        payload = self._get_public_json("/data-api/v3/liquidations/summary")
        data = payload.get("data") if isinstance(payload, dict) else None
        data = data if isinstance(data, dict) else {}
        return CoinMarketCapLiquidationsSummary(
            total=self._to_float(data.get("total")),
            longs=self._to_float(data.get("longs")),
            shorts=self._to_float(data.get("shorts")),
        )

    def get_liquidations_table(
        self,
        *,
        page: int = 1,
        page_size: int = 100,
        sort: str = "totalLiquidations1d",
        ascending_order: bool = False,
        interval: str = "1d",
    ) -> pd.DataFrame:
        payload = self._get_public_json(
            "/data-api/v3/liquidations/table",
            params={
                "page": str(page),
                "pageSize": str(page_size),
                "sort": sort,
                "ascendingOrder": str(ascending_order).lower(),
                "interval": interval,
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise RuntimeError(
                "CoinMarketCap returned an unexpected liquidations table shape."
            )
        rows = [
            {
                "rank": item.get("rank"),
                "coin_id": item.get("coinId"),
                "name": item.get("name"),
                "symbol": item.get("symbol"),
                "price": self._to_float(item.get("price")),
                "price_change_24h": self._to_float(item.get("priceChange24h")),
                "market_cap": self._to_float(item.get("marketCap")),
                "open_interest_usd": self._to_float(item.get("openInterestUsd")),
                "short_liquidations_usd": self._to_float(item.get("shortLiquidations")),
                "long_liquidations_usd": self._to_float(item.get("longLiquidations")),
                "total_liquidations_usd": self._to_float(item.get("totalLiquidations")),
            }
            for item in items
            if isinstance(item, dict)
        ]
        df = pd.DataFrame(rows)
        df.attrs["page"] = page
        df.attrs["page_size"] = page_size
        df.attrs["sort"] = sort
        df.attrs["ascending_order"] = ascending_order
        df.attrs["interval"] = interval
        df.attrs["total_count"] = (
            data.get("totalCount") if isinstance(data, dict) else None
        )
        return df

    def get_liquidation_chart(
        self,
        *,
        symbol: str | None = None,
        exchange: str | None = None,
    ) -> pd.DataFrame:
        chart_payload = self._load_liquidation_chart_payload(
            symbol=symbol,
            exchange=exchange,
        )
        series = chart_payload.get("series")
        if not isinstance(series, list):
            raise RuntimeError(
                "CoinMarketCap returned an unexpected liquidation chart shape."
            )

        series_map: dict[str, dict[int, float | None]] = {}
        for entry in series:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip().lower()
            points = entry.get("data")
            if not isinstance(points, list):
                continue
            series_map[name] = {
                int(point["x"]): self._to_float(point.get("y"))
                for point in points
                if isinstance(point, dict) and point.get("x") is not None
            }

        timestamps = sorted(
            {timestamp for points in series_map.values() for timestamp in points.keys()}
        )
        rows = []
        for timestamp in timestamps:
            long_value = series_map.get("long", {}).get(timestamp)
            short_value = series_map.get("short", {}).get(timestamp)
            price_value = (
                series_map.get("bitcoin price", {}).get(timestamp)
                if "bitcoin price" in series_map
                else None
            )
            rows.append(
                {
                    "timestamp": timestamp,
                    "date": pd.to_datetime(timestamp, unit="ms", utc=True),
                    "symbol": chart_payload.get("selected_coin_symbol"),
                    "coin_name": chart_payload.get("selected_coin_name"),
                    "exchange": chart_payload.get("selected_exchange"),
                    "long_liquidation_usd": long_value,
                    "short_liquidation_usd": abs(short_value)
                    if short_value is not None
                    else None,
                    "net_short_liquidation_usd": short_value,
                    "price_usd": price_value,
                    "price_series_name": chart_payload.get("price_series_name"),
                }
            )

        df = pd.DataFrame(rows)
        df.attrs["selected_coin_name"] = chart_payload.get("selected_coin_name")
        df.attrs["selected_coin_symbol"] = chart_payload.get("selected_coin_symbol")
        df.attrs["selected_exchange"] = chart_payload.get("selected_exchange")
        return df

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

    def _get_public_json(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        req = urllib.request.Request(
            url=f"{self.public_data_api_base_url}{endpoint}{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
                "Referer": self.liquidations_page_url,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"CoinMarketCap data-api HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"CoinMarketCap data-api request failed: {exc.reason}"
            ) from exc

        payload = json.loads(raw)
        status = payload.get("status") if isinstance(payload, dict) else None
        if isinstance(status, dict) and str(status.get("error_code", "0")) != "0":
            raise RuntimeError(f"CoinMarketCap data-api error: {status}")
        return payload

    def _load_liquidation_chart_payload(
        self,
        *,
        symbol: str | None,
        exchange: str | None,
    ) -> dict[str, Any]:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:
            raise RuntimeError(
                "Selenium is required to load CoinMarketCap liquidation charts."
            ) from exc

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1600,1200")
        driver = webdriver.Chrome(options=options)
        try:
            driver.get(self.liquidations_page_url)
            deadline = time.time() + self.timeout
            while time.time() < deadline:
                ready = driver.execute_script(
                    """
return Boolean(
  document.querySelector('.chart-wrapper') &&
  document.querySelectorAll('[role="combobox"]').length >= 2
);
"""
                )
                if ready:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(
                    "CoinMarketCap liquidation page did not finish rendering."
                )
            script = """
const normalize = (value) => String(value ?? "").trim().toLowerCase();
const getSelectProps = (index) => {
  const el = document.querySelectorAll('[role="combobox"]')[index];
  if (!el) return null;
  const fiberKey = Object.keys(el).find((key) => key.startsWith('__reactFiber$'));
  let fiber = fiberKey ? el[fiberKey] : null;
  for (let i = 0; fiber && i < 20; i += 1, fiber = fiber.return) {
    const typeName = fiber.type && (fiber.type.displayName || fiber.type.name);
    if (typeName === 'CMCUI_Select') {
      return fiber.memoizedProps || null;
    }
  }
  return null;
};
const selectOption = (index, query) => {
  if (!query) return null;
  const props = getSelectProps(index);
  if (!props || !Array.isArray(props.options) || typeof props.onChange !== 'function') {
    return { error: 'select props unavailable' };
  }
  const target = props.options.find((option) => {
    if (!option || typeof option !== 'object') return false;
    const haystacks = [
      option.value,
      option.name,
      option.symbol,
      option.id,
    ].map(normalize);
    return haystacks.includes(normalize(query));
  });
  if (!target) {
    return { error: `option not found: ${query}` };
  }
  props.onChange([target.value]);
  return { value: target.value, name: target.name || null, symbol: target.symbol || null };
};
const getChartPayload = () => {
  const chartEl = document.querySelector('.chart-wrapper');
  if (!chartEl) return null;
  const chartFiberKey = Object.keys(chartEl).find((key) => key.startsWith('__reactFiber$'));
  const chartFiber = chartFiberKey ? chartEl[chartFiberKey] : null;
  const props = chartFiber && chartFiber.return ? chartFiber.return.memoizedProps : null;
  const chartOptions = props && props.options ? props.options : null;
  const coinProps = getSelectProps(0);
  const exchangeProps = getSelectProps(1);
  return {
    selected_coin_name: coinProps && Array.isArray(coinProps.value) && coinProps.value[0] ? coinProps.value[0] : 'all',
    selected_coin_symbol: coinProps && Array.isArray(coinProps.options)
      ? ((coinProps.options.find((option) => option.value === (coinProps.value && coinProps.value[0])) || {}).symbol || null)
      : null,
    selected_exchange: exchangeProps && Array.isArray(exchangeProps.value) && exchangeProps.value[0] ? exchangeProps.value[0] : 'all',
    price_series_name: chartOptions && Array.isArray(chartOptions.series) && chartOptions.series[2] ? chartOptions.series[2].name : null,
    series: chartOptions ? chartOptions.series : null,
  };
};
return { selectOption, getChartPayload };
"""
            driver.execute_script(
                """
window.__CMC_LIQUIDATIONS_HELPERS__ = (() => {
%s
})();
"""
                % script
            )
            if symbol:
                result = driver.execute_script(
                    "return window.__CMC_LIQUIDATIONS_HELPERS__.selectOption(0, arguments[0]);",
                    symbol,
                )
                if isinstance(result, dict) and result.get("error"):
                    raise RuntimeError(
                        f"CoinMarketCap coin selection failed: {result['error']}"
                    )
                self._wait_for_chart_selection(
                    driver,
                    expected_coin_name=result.get("value"),
                    expected_exchange_name=None,
                )
            if exchange:
                result = driver.execute_script(
                    "return window.__CMC_LIQUIDATIONS_HELPERS__.selectOption(1, arguments[0]);",
                    exchange,
                )
                if isinstance(result, dict) and result.get("error"):
                    raise RuntimeError(
                        f"CoinMarketCap exchange selection failed: {result['error']}"
                    )
                self._wait_for_chart_selection(
                    driver,
                    expected_coin_name=None,
                    expected_exchange_name=result.get("value"),
                )
            chart_payload = driver.execute_script(
                "return window.__CMC_LIQUIDATIONS_HELPERS__.getChartPayload();"
            )
        finally:
            driver.quit()

        if not isinstance(chart_payload, dict):
            raise RuntimeError(
                "CoinMarketCap liquidation chart could not be extracted from the page."
            )
        return chart_payload

    def _wait_for_chart_selection(
        self,
        driver: Any,
        *,
        expected_coin_name: str | None,
        expected_exchange_name: str | None,
    ) -> None:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            state = driver.execute_script(
                "return window.__CMC_LIQUIDATIONS_HELPERS__.getChartPayload();"
            )
            if not isinstance(state, dict):
                time.sleep(0.25)
                continue
            coin_ok = (
                expected_coin_name is None
                or str(state.get("selected_coin_name")) == expected_coin_name
            )
            exchange_ok = (
                expected_exchange_name is None
                or str(state.get("selected_exchange")) == expected_exchange_name
            )
            series = state.get("series")
            if coin_ok and exchange_ok and isinstance(series, list) and series:
                return
            time.sleep(0.25)
        raise RuntimeError("CoinMarketCap chart selection did not settle in time.")

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
    print(client.get_liquidation_chart(symbol="ALT", exchange="All Exchanges"))
