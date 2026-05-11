from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request

import pandas as pd
from pydantic import BaseModel

from src.settings import app_settings


class BinanceTicker24h(BaseModel):
    symbol: str
    base_asset: str
    last_price: float | None
    price_change_percent: float | None
    quote_volume: float | None


class BinanceFuturesTicker24h(BaseModel):
    symbol: str
    base_asset: str
    last_price: float | None
    price_change_percent: float | None
    quote_volume: float | None


class BinanceKline(BaseModel):
    open_time_ms: int
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float | None
    volume: float | None
    close_time_ms: int


class BinanceOpenInterestHistoryPoint(BaseModel):
    symbol: str
    base_asset: str
    timestamp_ms: int
    open_interest: float | None
    open_interest_value: float | None


class BinanceTakerBuySellVolumePoint(BaseModel):
    symbol: str
    base_asset: str
    timestamp_ms: int
    buy_sell_ratio: float | None
    buy_volume: float | None
    sell_volume: float | None


class CryptoMarket24hSummary(BaseModel):
    btc_price_change_percent: float | None
    btc_last_price: float | None
    market_direction: str
    btc_direction: str

    @property
    def sentence(self) -> str:
        btc_change = (
            "N/A"
            if self.btc_price_change_percent is None
            else f"{abs(self.btc_price_change_percent):.2f}%"
        )
        return (
            f"Crypto market was {self.market_direction} over the past 24H, "
            f"BTC was {self.btc_direction} {btc_change} on the day."
        )


class BinanceClient:
    DEFAULT_HEATMAP_EXCLUDED_BASE_ASSETS = frozenset(
        {
            "AEUR",
            "BUSD",
            "DAI",
            "EURI",
            "EUR",
            "FDUSD",
            "RLUSD",
            "TUSD",
            "USDC",
            "USDE",
            "USDP",
            "USD",
            "USD1",
            "XUSD",
        }
    )

    def __init__(
        self,
        *,
        base_url: str | None = None,
        futures_base_url: str | None = None,
        timeout: float = 10.0,
        api_key: str | None = None,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.binance_base_url
        resolved_futures_base_url = (
            futures_base_url or app_settings.binance_futures_base_url
        )
        self.base_url = resolved_base_url.rstrip("/")
        self.futures_base_url = resolved_futures_base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.user_agent = user_agent

    def get_24h_ticker(self, symbol: str = "BTCUSDT") -> BinanceTicker24h:
        payload = self._get("/api/v3/ticker/24hr", params={"symbol": symbol.upper()})
        if not isinstance(payload, dict):
            raise RuntimeError("Binance returned an unexpected ticker response shape.")
        return self._parse_ticker(payload)

    def get_24h_tickers(
        self,
        symbols: Iterable[str] | None = None,
    ) -> list[BinanceTicker24h]:
        params = None
        if symbols is not None:
            params = {
                "symbols": json.dumps(
                    [symbol.upper() for symbol in symbols],
                    separators=(",", ":"),
                )
            }

        payload = self._get("/api/v3/ticker/24hr", params=params)
        if isinstance(payload, dict):
            return [self._parse_ticker(payload)]
        if not isinstance(payload, list):
            raise RuntimeError("Binance returned an unexpected ticker response shape.")
        return [self._parse_ticker(item) for item in payload if isinstance(item, dict)]

    def get_crypto_market_24h_summary(
        self,
        *,
        symbol: str = "BTCUSDT",
    ) -> CryptoMarket24hSummary:
        ticker = self.get_24h_ticker(symbol)
        btc_change = ticker.price_change_percent
        market_direction = self._direction_word(btc_change)
        btc_direction = self._direction_word(btc_change)
        return CryptoMarket24hSummary(
            btc_price_change_percent=btc_change,
            btc_last_price=ticker.last_price,
            market_direction=market_direction,
            btc_direction=btc_direction,
        )

    def get_usdt_market_heatmap_data(
        self,
        *,
        top_n: int = 50,
        quote_asset: str = "USDT",
        include_symbols: Iterable[str] | None = None,
        excluded_base_assets: Iterable[str] | None = None,
    ) -> pd.DataFrame:
        tickers = self.get_24h_tickers(include_symbols)
        excluded = {
            asset.upper()
            for asset in (
                excluded_base_assets or self.DEFAULT_HEATMAP_EXCLUDED_BASE_ASSETS
            )
        }
        rows = [
            ticker.model_dump()
            for ticker in tickers
            if ticker.symbol.endswith(quote_asset.upper())
            and ticker.quote_volume is not None
            and ticker.quote_volume > 0
            and ticker.base_asset.isascii()
            and ticker.base_asset not in excluded
            and not self._is_leveraged_token(ticker.base_asset)
        ]
        df = pd.DataFrame(
            rows,
            columns=[
                "symbol",
                "base_asset",
                "last_price",
                "price_change_percent",
                "quote_volume",
            ],
        )
        if df.empty:
            return df
        return (
            df.sort_values(by="quote_volume", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

    def get_futures_24h_ticker(self, symbol: str) -> BinanceFuturesTicker24h:
        payload = self._get_futures(
            "/fapi/v1/ticker/24hr",
            params={"symbol": symbol.upper()},
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Binance returned an unexpected futures ticker shape.")
        return self._parse_futures_ticker(payload)

    def get_usdt_perp_24h_quote_volume(self, base_asset: str) -> float | None:
        ticker = self.get_futures_24h_ticker(f"{base_asset.upper()}USDT")
        return ticker.quote_volume

    def get_klines(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        limit: int = 30,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[BinanceKline]:
        params: dict[str, str] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": str(limit),
        }
        if start_time_ms is not None:
            params["startTime"] = str(start_time_ms)
        if end_time_ms is not None:
            params["endTime"] = str(end_time_ms)

        payload = self._get("/api/v3/klines", params=params)
        if not isinstance(payload, list):
            raise RuntimeError("Binance returned an unexpected kline response shape.")
        return [self._parse_kline(item) for item in payload if isinstance(item, list)]

    def get_futures_klines(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        limit: int = 30,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[BinanceKline]:
        params: dict[str, str] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": str(limit),
        }
        if start_time_ms is not None:
            params["startTime"] = str(start_time_ms)
        if end_time_ms is not None:
            params["endTime"] = str(end_time_ms)

        payload = self._get_futures("/fapi/v1/klines", params=params)
        if not isinstance(payload, list):
            raise RuntimeError(
                "Binance returned an unexpected futures kline response shape."
            )
        return [self._parse_kline(item) for item in payload if isinstance(item, list)]

    def get_futures_open_interest_history(
        self,
        base_asset: str,
        *,
        period: str = "1d",
        limit: int = 30,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> pd.DataFrame:
        symbol = self._usdt_symbol(base_asset)
        params: dict[str, str] = {
            "symbol": symbol,
            "period": period,
            "limit": str(limit),
        }
        if start_time_ms is not None:
            params["startTime"] = str(start_time_ms)
        if end_time_ms is not None:
            params["endTime"] = str(end_time_ms)

        payload = self._get_futures("/futures/data/openInterestHist", params=params)
        if not isinstance(payload, list):
            raise RuntimeError("Binance returned an unexpected open-interest shape.")

        rows = [
            self._parse_open_interest_history_point(symbol, item).model_dump()
            for item in payload
            if isinstance(item, dict)
        ]
        df = pd.DataFrame(
            rows,
            columns=[
                "symbol",
                "base_asset",
                "timestamp_ms",
                "open_interest",
                "open_interest_value",
            ],
        )
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
        return df.sort_values(by="date").reset_index(drop=True)

    def get_futures_taker_buy_sell_volume(
        self,
        base_asset: str,
        *,
        period: str = "1d",
        limit: int = 30,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> pd.DataFrame:
        symbol = self._usdt_symbol(base_asset)
        params: dict[str, str] = {
            "symbol": symbol,
            "period": period,
            "limit": str(limit),
        }
        if start_time_ms is not None:
            params["startTime"] = str(start_time_ms)
        if end_time_ms is not None:
            params["endTime"] = str(end_time_ms)

        payload = self._get_futures("/futures/data/takerlongshortRatio", params=params)
        if not isinstance(payload, list):
            raise RuntimeError("Binance returned an unexpected taker volume shape.")

        rows = [
            self._parse_taker_buy_sell_volume_point(symbol, item).model_dump()
            for item in payload
            if isinstance(item, dict)
        ]
        df = pd.DataFrame(
            rows,
            columns=[
                "symbol",
                "base_asset",
                "timestamp_ms",
                "buy_sell_ratio",
                "buy_volume",
                "sell_volume",
            ],
        )
        if df.empty:
            return df
        # Binance's UI labels taker-volume daily buckets by the report day,
        # while the public endpoint timestamp is the bucket start.
        df["date"] = pd.to_datetime(
            df["timestamp_ms"], unit="ms", utc=True
        ) + pd.Timedelta(days=1)
        return df.sort_values(by="date").reset_index(drop=True)

    def _get(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> Any:
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
            raise RuntimeError(f"Binance API HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Binance API request failed: {exc.reason}") from exc

        return json.loads(raw)

    def _get_futures(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        query = f"?{urlencode(params)}" if params else ""
        req = urllib.request.Request(
            url=f"{self.futures_base_url}{endpoint}{query}",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Binance Futures API HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Binance Futures API request failed: {exc.reason}"
            ) from exc

        return json.loads(raw)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
        return headers

    @classmethod
    def _parse_ticker(cls, payload: dict[str, Any]) -> BinanceTicker24h:
        symbol = str(payload.get("symbol", ""))
        return BinanceTicker24h(
            symbol=symbol,
            base_asset=cls._base_asset(symbol),
            last_price=cls._to_float(payload.get("lastPrice")),
            price_change_percent=cls._to_float(payload.get("priceChangePercent")),
            quote_volume=cls._to_float(payload.get("quoteVolume")),
        )

    @classmethod
    def _parse_futures_ticker(cls, payload: dict[str, Any]) -> BinanceFuturesTicker24h:
        symbol = str(payload.get("symbol", ""))
        return BinanceFuturesTicker24h(
            symbol=symbol,
            base_asset=cls._base_asset(symbol),
            last_price=cls._to_float(payload.get("lastPrice")),
            price_change_percent=cls._to_float(payload.get("priceChangePercent")),
            quote_volume=cls._to_float(payload.get("quoteVolume")),
        )

    @classmethod
    def _parse_kline(cls, payload: list[Any]) -> BinanceKline:
        if len(payload) < 7:
            raise RuntimeError("Binance returned an unexpected kline row shape.")
        return BinanceKline(
            open_time_ms=int(payload[0]),
            open_price=cls._to_float(payload[1]),
            high_price=cls._to_float(payload[2]),
            low_price=cls._to_float(payload[3]),
            close_price=cls._to_float(payload[4]),
            volume=cls._to_float(payload[5]),
            close_time_ms=int(payload[6]),
        )

    @classmethod
    def _parse_open_interest_history_point(
        cls,
        symbol: str,
        payload: dict[str, Any],
    ) -> BinanceOpenInterestHistoryPoint:
        resolved_symbol = str(payload.get("symbol") or symbol)
        return BinanceOpenInterestHistoryPoint(
            symbol=resolved_symbol,
            base_asset=cls._base_asset(resolved_symbol),
            timestamp_ms=int(payload["timestamp"]),
            open_interest=cls._to_float(payload.get("sumOpenInterest")),
            open_interest_value=cls._to_float(payload.get("sumOpenInterestValue")),
        )

    @classmethod
    def _parse_taker_buy_sell_volume_point(
        cls,
        symbol: str,
        payload: dict[str, Any],
    ) -> BinanceTakerBuySellVolumePoint:
        return BinanceTakerBuySellVolumePoint(
            symbol=symbol,
            base_asset=cls._base_asset(symbol),
            timestamp_ms=int(payload["timestamp"]),
            buy_sell_ratio=cls._to_float(payload.get("buySellRatio")),
            buy_volume=cls._to_float(payload.get("buyVol")),
            sell_volume=cls._to_float(payload.get("sellVol")),
        )

    @staticmethod
    def _base_asset(symbol: str, quote_asset: str = "USDT") -> str:
        if symbol.endswith(quote_asset):
            return symbol[: -len(quote_asset)]
        return symbol

    @staticmethod
    def _usdt_symbol(base_asset: str) -> str:
        symbol = base_asset.upper()
        return symbol if symbol.endswith("USDT") else f"{symbol}USDT"

    @staticmethod
    def _direction_word(value: float | None) -> str:
        if value is None or value == 0:
            return "flat"
        return "up" if value > 0 else "down"

    @staticmethod
    def _is_leveraged_token(base_asset: str) -> bool:
        return base_asset.endswith(("UP", "DOWN", "BULL", "BEAR"))

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    from src.utils.visualization import crypto_market_heatmap_to_png

    client = BinanceClient()

    summary = client.get_crypto_market_24h_summary()
    print(summary.sentence)

    df = client.get_usdt_market_heatmap_data(top_n=20)
    crypto_market_heatmap_to_png(df, "results/market/binance_crypto_heatmap.png")
