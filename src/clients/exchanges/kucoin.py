from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
import urllib.error
import urllib.request
from tqdm import tqdm  # pyrefly: ignore[untyped-import]

import pandas as pd
from src.settings import app_settings


class KucoinClient:
    def __init__(
        self,
        *,
        spot_base_url: str | None = None,
        futures_base_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.spot_base_url = (
            spot_base_url.rstrip("/")
            if spot_base_url
            else app_settings.kucoin_spot_base_url
        )
        self.futures_base_url = (
            futures_base_url.rstrip("/")
            if futures_base_url
            else app_settings.kucoin_future_base_url
        )
        self.timeout = timeout

    def get_history_volume(self, tokens: list[str], days: int = 30) -> pd.DataFrame:
        """
        Fetch daily 24h USD volume history for each token (spot and/or perp).

        Each token is resolved as:
          - perp  if it ends with "USDTM" (e.g. "BTCUSDTM")
          - spot  otherwise              (e.g. "BTC" → "BTC-USDT")

        Returns columns: date (date), product (str), base (str), usd_volume_24h (float)
        Errors per token/day are stored as NaN in usd_volume_24h.
        """
        end_dt = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_dt = end_dt - timedelta(days=days)

        all_rows: list[dict[str, Any]] = []
        # use tqdm
        for raw in tqdm(tokens, desc="Fetching history volume"):
            raw = raw.upper()
            if self._is_perp(raw):
                rows = self._fetch_history_futures(raw, start_dt, end_dt)
            else:
                symbol = f"{raw}-USDT"
                rows = self._fetch_history_spot(symbol, raw, start_dt, end_dt)
            all_rows.extend(rows)

        return pd.DataFrame(
            all_rows, columns=["date", "product", "base", "usd_volume_24h"]
        )

    def get_trading_volume(self, tokens: list[str]) -> pd.DataFrame:
        """
        Fetch 24h USD volume for each token (spot and/or perp) and return a DataFrame.

        Each token is resolved as:
          - perp  if it ends with "USDTM" (e.g. "BTCUSDTM")
          - spot  otherwise              (e.g. "BTC" → "BTC-USDT")

        Returns columns: timestamp_utc (datetime), product (str), base (str), usd_volume_24h (float)
        Errors per token are stored as NaN in usd_volume_24h.
        """
        rows = self._fetch_rows(tokens)
        stamp = rows[0]["timestamp_utc"] if rows else self._utc_ts()

        # parse the "YYYY-MM-DD_HH-MM-SS" string produced by _utc_ts()
        ts = datetime.strptime(stamp, "%Y-%m-%d_%H-%M-%S").replace(tzinfo=timezone.utc)

        records = [
            {
                "timestamp_utc": ts,
                "product": r["product"],
                "base": r["base"],
                "usd_volume_24h": r[
                    "usd_volume_24h"
                ],  # None on error → NaN in DataFrame
            }
            for r in rows
        ]

        return pd.DataFrame(
            records, columns=["timestamp_utc", "product", "base", "usd_volume_24h"]
        )

    def get_spot_quote_volume_history(
        self,
        symbol: str,
        *,
        days: int,
        report_date: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")

        end_dt = _resolve_report_end(report_date)
        start_dt = end_dt - timedelta(days=days - 1)
        payload = self._get(
            self.spot_base_url,
            "/api/v1/market/candles",
            params={
                "symbol": symbol.upper(),
                "type": "1day",
                "startAt": str(int(start_dt.timestamp())),
                "endAt": str(int((end_dt + timedelta(days=1)).timestamp())),
            },
        )
        if str(payload.get("code")) != "200000":
            raise ValueError(f"KuCoin spot kline error for {symbol.upper()}: {payload}")

        rows: list[dict[str, object]] = []
        for item in payload.get("data") or []:
            if not isinstance(item, list) or len(item) < 7:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(int(item[0]), unit="s", utc=True)
                    .floor("D")
                    .tz_localize(None),
                    "quote_volume": self._to_float(item[6]),
                }
            )
        return pd.DataFrame(rows, columns=["date", "quote_volume"]).sort_values(
            by="date"
        )

    def get_spot_order_book(self, symbol: str) -> dict[str, Any]:
        payload = self._get(
            self.spot_base_url,
            "/api/v1/market/orderbook/level2_100",
            params={"symbol": symbol.upper()},
        )
        if str(payload.get("code")) != "200000":
            raise ValueError(f"KuCoin order book error for {symbol.upper()}: {payload}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("KuCoin returned an unexpected order-book shape.")
        return {
            "exchange": "kucoin",
            "symbol": symbol.upper(),
            "bids": self._parse_price_levels(data.get("bids")),
            "asks": self._parse_price_levels(data.get("asks")),
            "timestamp_ms": self._to_int(data.get("time")),
        }

    def get_spot_today_trading_volume(
        self,
        symbol: str,
    ) -> float:
        start_at, end_at = _today_window_bounds_seconds()
        return self._sum_spot_kline_turnover(
            symbol.upper(),
            start_at=start_at,
            end_at=end_at,
            candle_type="1min",
        )

    def get_futures_today_trading_volume(self, contract_id: str) -> float:
        start_at_ms, end_at_ms = _today_window_bounds_ms()
        payload = self._get(
            self.futures_base_url,
            "/api/v1/kline/query",
            params={
                "symbol": contract_id.upper(),
                "granularity": "1",
                "from": str(start_at_ms),
                "to": str(end_at_ms),
            },
        )
        if str(payload.get("code")) not in {"200", "200000"}:
            raise ValueError(
                f"KuCoin futures today trading volume error for {contract_id.upper()}: {payload}"
            )

        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("KuCoin returned an unexpected futures kline shape.")

        total_volume = 0.0
        for row in data:
            if not isinstance(row, list) or len(row) < 7:
                continue
            candle_ts = self._to_int(row[0])
            if candle_ts is None or candle_ts < start_at_ms or candle_ts > end_at_ms:
                continue
            total_volume += self._to_float(row[6]) or 0.0
        return total_volume

    # ---------- Private: history fetching ----------

    def _fetch_history_spot(
        self, symbol: str, base: str, start_dt: datetime, end_dt: datetime
    ) -> list[dict[str, Any]]:
        """
        GET /api/v1/market/candles with type=1day.
        Response row: [ts_seconds, open, close, high, low, volume, turnover]
        turnover is the USDT notional — that's our usd_volume_24h.
        """
        try:
            j = self._get(
                self.spot_base_url,
                "/api/v1/market/candles",
                params={
                    "symbol": symbol,
                    "type": "1day",
                    "startAt": str(int(start_dt.timestamp())),
                    "endAt": str(int(end_dt.timestamp())),
                },
            )
            if str(j.get("code")) != "200000":
                raise ValueError(f"KuCoin spot kline error for {symbol}: {j}")
            relist_day_start = self._spot_trading_start_day_start(symbol)
            rows: list[dict[str, Any]] = []
            for row in j.get("data") or []:
                if not isinstance(row, list) or len(row) < 7:
                    continue
                candle_ts = self._to_int(row[0])
                if candle_ts is None:
                    continue
                # Reused spot symbols can expose old candles.
                # tradingStartTime marks the current listing.
                if relist_day_start is not None and candle_ts < relist_day_start:
                    continue
                rows.append(
                    {
                        "date": datetime.fromtimestamp(candle_ts, tz=timezone.utc),
                        "product": "spot",
                        "base": base,
                        "usd_volume_24h": (self._to_float(row[6]) or 0.0)
                        * 2,  # turnover = USDT notional
                    }
                )
            return rows
        except Exception:
            # Return one error row per day in the range so the token is still represented
            return [
                {
                    "date": (start_dt + timedelta(days=i)),
                    "product": "spot",
                    "base": base,
                    "usd_volume_24h": None,
                }
                for i in range((end_dt - start_dt).days)
            ]

    def _spot_trading_start_day_start(self, symbol: str) -> int | None:
        """Return UTC midnight seconds for the current KuCoin spot listing, if exposed."""
        try:
            payload = self._get(self.spot_base_url, f"/api/v2/symbols/{symbol}")
        except Exception:
            return None
        if str(payload.get("code")) != "200000":
            return None

        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        trading_start_ms = self._to_int(data.get("tradingStartTime"))
        if trading_start_ms is None:
            return None

        trading_start = datetime.fromtimestamp(trading_start_ms / 1000, tz=timezone.utc)
        return int(
            trading_start.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        )

    def _fetch_history_futures(
        self, contract_id: str, start_dt: datetime, end_dt: datetime
    ) -> list[dict[str, Any]]:
        """
        GET /api/v1/kline/query with granularity=1440 (daily in minutes).
        Response row: [ts_ms, open, high, low, close, volume, turnover]
        turnover is the USDT notional — that's our usd_volume_24h.
        """
        try:
            j = self._get(
                self.futures_base_url,
                "/api/v1/kline/query",
                params={
                    "symbol": contract_id,
                    "granularity": "1440",  # daily candles (minutes)
                    "from": str(int(start_dt.timestamp() * 1000)),
                    "to": str(int(end_dt.timestamp() * 1000)),
                },
            )
            if str(j.get("code")) != "200000":
                raise ValueError(f"KuCoin futures kline error for {contract_id}: {j}")
            return [
                {
                    "date": datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                    "product": "perp",
                    "base": contract_id,
                    "usd_volume_24h": (self._to_float(row[6]) or 0.0)
                    * 2,  # turnover = USDT notional
                }
                for row in (j.get("data") or [])
            ]
        except Exception:
            return [
                {
                    "date": (start_dt + timedelta(days=i)),
                    "product": "perp",
                    "base": contract_id,
                    "usd_volume_24h": None,
                }
                for i in range((end_dt - start_dt).days)
            ]

    # ---------- Private: data fetching ----------

    def _fetch_rows(self, tokens: list[str]) -> list[dict[str, Any]]:
        """Fetch one row per token; catches per-token errors so one failure doesn't abort others."""
        rows: list[dict[str, Any]] = []
        stamp = self._utc_ts()

        for raw in tokens:
            raw = raw.upper()
            if self._is_perp(raw):
                try:
                    vol = self._futures_turnover_24h(raw)
                    rows.append(
                        {
                            "timestamp_utc": stamp,
                            "base": raw,
                            "product": "perp",
                            "usd_volume_24h": vol,
                        }
                    )
                except Exception as exc:
                    rows.append(
                        {
                            "timestamp_utc": stamp,
                            "base": raw,
                            "product": "perp",
                            "usd_volume_24h": None,
                            "error": str(exc),
                        }
                    )
            else:
                symbol = f"{raw}-USDT"
                try:
                    vol = self._spot_turnover_24h(symbol)
                    rows.append(
                        {
                            "timestamp_utc": stamp,
                            "base": raw,
                            "product": "spot",
                            "usd_volume_24h": vol,
                        }
                    )
                except Exception as exc:
                    rows.append(
                        {
                            "timestamp_utc": stamp,
                            "base": raw,
                            "product": "spot",
                            "usd_volume_24h": None,
                            "error": str(exc),
                        }
                    )

        return rows

    def _spot_turnover_24h(self, symbol: str) -> float:
        """GET /api/v1/market/stats → data.volValue (24h USDT notional)."""
        j = self._get(
            self.spot_base_url, "/api/v1/market/stats", params={"symbol": symbol}
        )
        if str(j.get("code")) != "200000":
            raise ValueError(f"KuCoin spot error for {symbol}: {j}")
        return self._to_float(j.get("data", {}).get("volValue")) or 0.0

    def _futures_turnover_24h(self, contract_id: str) -> float:
        """GET /api/v1/contracts/{contract_id} → data.turnoverOf24h (24h USDT notional)."""
        j = self._get(self.futures_base_url, f"/api/v1/contracts/{contract_id}")
        if str(j.get("code")) != "200000":
            raise ValueError(f"KuCoin futures error for {contract_id}: {j}")
        return self._to_float(j.get("data", {}).get("turnoverOf24h")) or 0.0

    def _sum_spot_kline_turnover(
        self,
        symbol: str,
        *,
        start_at: int,
        end_at: int,
        candle_type: str,
    ) -> float:
        payload = self._get(
            self.spot_base_url,
            "/api/v1/market/candles",
            params={
                "symbol": symbol,
                "type": candle_type,
                "startAt": str(start_at),
                "endAt": str(end_at),
            },
        )
        if str(payload.get("code")) != "200000":
            raise ValueError(
                f"KuCoin spot trading volume error for {symbol}: {payload}"
            )

        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("KuCoin returned an unexpected spot kline shape.")

        total_volume = 0.0
        for row in data:
            if not isinstance(row, list) or len(row) < 7:
                continue
            candle_ts = self._to_int(row[0])
            if candle_ts is None or candle_ts < start_at or candle_ts > end_at:
                continue
            total_volume += self._to_float(row[6]) or 0.0
        return total_volume

    def _get(
        self, base_url: str, endpoint: str, params: dict[str, str] | None = None
    ) -> Any:
        """Generic JSON GET; raises ValueError on HTTP/network/parse errors."""
        query = f"?{urlencode(params)}" if params else ""
        req = urllib.request.Request(
            url=f"{base_url}{endpoint}{query}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ValueError(
                f"HTTP {exc.code} from {base_url}{endpoint}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ValueError(
                f"Network error from {base_url}{endpoint}: {exc.reason}"
            ) from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON from {base_url}{endpoint}: {raw[:200]}"
            ) from exc

    # ---------- Private: static helpers ----------

    @staticmethod
    def _is_perp(symbol: str) -> bool:
        """True if symbol is a KuCoin perpetual futures contract (ends with USDTM)."""
        return symbol.endswith("USDTM")

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Safe float conversion; returns None on failure."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _utc_ts() -> str:
        """Current UTC timestamp as YYYY-MM-DD_HH-MM-SS."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

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


def _resolve_report_end(
    report_date: str | pd.Timestamp | None,
) -> datetime:
    if report_date is None:
        return datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    timestamp = pd.Timestamp(report_date)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    timestamp = timestamp.normalize()
    return timestamp.to_pydatetime()


def _today_window_bounds_seconds() -> tuple[int, int]:
    start_dt = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_dt = datetime.now(timezone.utc)
    return int(start_dt.timestamp()), int(end_dt.timestamp())


def _today_window_bounds_ms() -> tuple[int, int]:
    start_dt = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_dt = datetime.now(timezone.utc)
    return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)


if __name__ == "__main__":
    client = KucoinClient()
    print(client.get_spot_today_trading_volume("GRAM-USDT"))
    # print(client.get_futures_today_trading_volume("XBTUSDTM"))
