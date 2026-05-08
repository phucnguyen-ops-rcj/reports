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

    def get_spot_symbols(self, market: str | None = None) -> list[dict[str, Any]]:
        params = {"market": market} if market else None
        j = self._get(self.spot_base_url, "/api/v1/symbols", params=params)
        if str(j.get("code")) != "200000":
            raise ValueError(f"KuCoin spot symbols error: {j}")
        data = j.get("data") or []
        return [item for item in data if isinstance(item, dict)]

    def get_spot_symbol_rules(self, symbol: str) -> dict[str, Any]:
        resolved_symbol = symbol.upper()
        matches = [
            item
            for item in self.get_spot_symbols()
            if str(item.get("symbol", "")).upper() == resolved_symbol
        ]
        if not matches:
            raise ValueError(f"KuCoin spot symbol rules not found for {symbol}.")
        item = matches[0]
        return {
            "symbol": item.get("symbol", resolved_symbol),
            "status": "TRADING" if item.get("enableTrading", True) else "DISABLED",
            "min_notional": self._to_float(item.get("minFunds")),
            "min_qty": self._to_float(
                item.get("baseMinSize") or item.get("tradeMinSize")
            ),
            "step_size": self._to_float(
                item.get("baseIncrement") or item.get("amountMinPrecision")
            ),
            "tick_size": self._to_float(
                item.get("priceIncrement") or item.get("priceMinPrecision")
            ),
        }

    def get_futures_contract(self, contract_id: str) -> dict[str, Any]:
        j = self._get(self.futures_base_url, f"/api/v1/contracts/{contract_id.upper()}")
        if str(j.get("code")) != "200000":
            raise ValueError(f"KuCoin futures contract error for {contract_id}: {j}")
        data = j.get("data")
        if not isinstance(data, dict):
            raise ValueError(
                f"KuCoin futures contract returned unexpected data for {contract_id}: {j}"
            )
        return data

    def get_futures_symbol_rules(self, contract_id: str) -> dict[str, Any]:
        data = self.get_futures_contract(contract_id)
        return {
            "symbol": data.get("symbol", contract_id.upper()),
            "status": data.get("status"),
            "min_notional": None,
            "min_qty": self._to_float(data.get("lotSize")),
            "step_size": self._to_float(data.get("lotSize")),
            "tick_size": self._to_float(data.get("tickSize")),
            "multiplier": self._to_float(data.get("multiplier")),
        }

    def get_spot_order_book(self, symbol: str, *, limit: int = 100) -> dict[str, Any]:
        resolved_symbol = symbol.upper()
        attempts = [
            (
                "/api/v1/market/orderbook",
                {"symbol": resolved_symbol, "limit": str(limit)},
            ),
            ("/api/v1/market/orderbook/level2_100", {"symbol": resolved_symbol}),
            ("/api/v1/market/orderbook/level2_20", {"symbol": resolved_symbol}),
        ]
        last_error: Exception | None = None
        for endpoint, params in attempts:
            try:
                j = self._get(self.spot_base_url, endpoint, params=params)
                if str(j.get("code")) != "200000":
                    raise ValueError(f"KuCoin spot order book error: {j}")
                data = j.get("data")
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                last_error = exc
        raise ValueError(f"KuCoin spot order book failed for {symbol}: {last_error}")

    def get_futures_order_book(
        self, contract_id: str, *, limit: int = 100
    ) -> dict[str, Any]:
        resolved_contract_id = contract_id.upper()
        attempts = [
            (
                "/api/v1/contract/orderbook",
                {"symbol": resolved_contract_id, "limit": str(limit)},
            ),
            ("/api/v1/level2/depth100", {"symbol": resolved_contract_id}),
            ("/api/v1/level2/depth20", {"symbol": resolved_contract_id}),
        ]
        last_error: Exception | None = None
        for endpoint, params in attempts:
            try:
                j = self._get(self.futures_base_url, endpoint, params=params)
                if str(j.get("code")) != "200000":
                    raise ValueError(f"KuCoin futures order book error: {j}")
                data = j.get("data")
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                last_error = exc
        raise ValueError(
            f"KuCoin futures order book failed for {contract_id}: {last_error}"
        )

    def get_spot_klines(
        self,
        symbol: str,
        *,
        interval: str = "1min",
        start_at_s: int | None = None,
        end_at_s: int | None = None,
    ) -> list[list[Any]]:
        params: dict[str, str] = {"symbol": symbol.upper(), "type": interval}
        if start_at_s is not None:
            params["startAt"] = str(start_at_s)
        if end_at_s is not None:
            params["endAt"] = str(end_at_s)
        j = self._get(self.spot_base_url, "/api/v1/market/candles", params=params)
        if str(j.get("code")) != "200000":
            raise ValueError(f"KuCoin spot kline error for {symbol}: {j}")
        return [row for row in (j.get("data") or []) if isinstance(row, list)]

    def get_futures_klines(
        self,
        contract_id: str,
        *,
        granularity: int = 1,
        start_at_ms: int | None = None,
        end_at_ms: int | None = None,
    ) -> list[list[Any]]:
        params: dict[str, str] = {
            "symbol": contract_id.upper(),
            "granularity": str(granularity),
        }
        if start_at_ms is not None:
            params["from"] = str(start_at_ms)
        if end_at_ms is not None:
            params["to"] = str(end_at_ms)
        j = self._get(self.futures_base_url, "/api/v1/kline/query", params=params)
        if str(j.get("code")) != "200000":
            raise ValueError(f"KuCoin futures kline error for {contract_id}: {j}")
        return [row for row in (j.get("data") or []) if isinstance(row, list)]

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
            return [
                {
                    "date": datetime.fromtimestamp(int(row[0]), tz=timezone.utc),
                    "product": "spot",
                    "base": base,
                    "usd_volume_24h": (self._to_float(row[6]) or 0.0)
                    * 2,  # turnover = USDT notional
                }
                for row in (j.get("data") or [])
            ]
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


if __name__ == "__main__":
    client = KucoinClient()
    df = client.get_history_volume(["CHIP"])
    print(df.usd_volume_24h.sum())
    print(df)
