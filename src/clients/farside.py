from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin
import urllib.error
import urllib.request

import pandas as pd

from src.settings import app_settings


class _FarsideTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_etf_table = False
        self._in_row = False
        self._in_cell = False
        self._current_row: list[str] = []
        self._current_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table" and "etf" in (attrs_dict.get("class") or "").split():
            self._in_etf_table = True
            return
        if not self._in_etf_table:
            return
        if tag == "tr":
            self._in_row = True
            self._current_row = []
            return
        if tag in {"td", "th"} and self._in_row:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if not self._in_etf_table:
            return
        if tag in {"td", "th"} and self._in_cell:
            self._current_row.append(" ".join("".join(self._current_cell).split()))
            self._in_cell = False
            return
        if tag == "tr" and self._in_row:
            if self._current_row:
                self.rows.append(self._current_row)
            self._in_row = False
            return
        if tag == "table":
            self._in_etf_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)


class FarsideClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.farside_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    def get_etf_flow_table(self, asset: str) -> pd.DataFrame:
        html = self._get_html(f"/{asset.lower()}/")
        rows = self._parse_etf_rows(html)
        if len(rows) < 4:
            raise RuntimeError(f"Farside returned no {asset.upper()} ETF flow rows.")

        headers = self._resolve_headers(rows)
        records: list[dict[str, Any]] = []
        for row in rows[3:]:
            if len(row) != len(headers):
                continue
            record = dict(zip(headers, row, strict=False))
            date = self._parse_date(record.get("date", ""))
            if date is None:
                continue
            parsed_record: dict[str, Any] = {"date": date}
            for key, value in record.items():
                if key == "date":
                    continue
                parsed_record[key] = self._parse_amount(value)
            records.append(parsed_record)

        if not records:
            raise RuntimeError(
                f"Farside returned no parseable {asset.upper()} ETF flow rows."
            )

        return pd.DataFrame(records).sort_values(by="date").reset_index(drop=True)

    def get_etf_net_flows(
        self,
        asset: str,
        *,
        days: int | None = None,
        end_date: str | datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        df = self.get_etf_flow_table(asset)
        net_flows = df.loc[:, ["date", "total"]].copy()
        if end_date is not None:
            net_flows = net_flows[net_flows["date"] <= pd.Timestamp(end_date)]
        net_flows["asset"] = asset.upper()
        if days is not None:
            net_flows = net_flows.tail(days)
        return net_flows.reset_index(drop=True)

    def get_btc_eth_etf_net_flows(
        self,
        *,
        days: int | None = None,
        end_date: str | datetime | pd.Timestamp | None = None,
    ) -> dict[str, pd.DataFrame]:
        return {
            "BTC": self.get_etf_net_flows("btc", days=days, end_date=end_date),
            "ETH": self.get_etf_net_flows("eth", days=days, end_date=end_date),
        }

    def _get_html(self, endpoint: str) -> str:
        req = urllib.request.Request(
            url=urljoin(f"{self.base_url}/", endpoint.lstrip("/")),
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Farside HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Farside request failed: {exc.reason}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }

    @staticmethod
    def _parse_etf_rows(html: str) -> list[list[str]]:
        parser = _FarsideTableParser()
        parser.feed(html)
        return parser.rows

    @staticmethod
    def _resolve_headers(rows: list[list[str]]) -> list[str]:
        symbol_row = rows[1]
        headers = ["date", *[cell.lower() for cell in symbol_row[1:-1]], "total"]
        return [header.replace(" ", "_") for header in headers]

    @staticmethod
    def _parse_date(value: str) -> datetime | None:
        try:
            return datetime.strptime(value, "%d %b %Y")
        except ValueError:
            return None

    @staticmethod
    def _parse_amount(value: str) -> float | None:
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = f"-{cleaned[1:-1]}"
        try:
            return float(cleaned)
        except ValueError:
            return None
