from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image
from pydantic import BaseModel

from src.settings import app_settings


class CoinSharesReport(BaseModel):
    title: str
    url: str
    published_at: datetime | None
    image_urls: list[str]


class CoinSharesClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        user_agent: str = "reports/1.0",
    ) -> None:
        resolved_base_url = base_url or app_settings.coinshares_base_url
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    def get_latest_weekly_report(self) -> CoinSharesReport:
        feed_xml = self._get_text("/feed")
        root = ET.fromstring(feed_xml)
        content_ns = "{http://purl.org/rss/1.0/modules/content/}"

        for item in root.findall("./channel/item"):
            title = self._text(item.find("title"))
            if "digital asset fund flows weekly report" not in title.lower():
                continue

            link = self._strip_query(self._text(item.find("link")))
            published_at = self._parse_rss_date(self._text(item.find("pubDate")))
            content = self._text(item.find(f"{content_ns}encoded"))
            image_urls = self._extract_image_urls(content)
            return CoinSharesReport(
                title=title,
                url=link,
                published_at=published_at,
                image_urls=image_urls,
            )

        raise RuntimeError("No CoinShares weekly fund-flow report found in RSS feed.")

    def download_latest_flow_table_image(
        self,
        output_path: str | Path,
    ) -> Path:
        report = self.get_latest_weekly_report()
        if not report.image_urls:
            raise RuntimeError(
                f"No images found for latest CoinShares report: {report.url}"
            )

        image_url = self._select_flow_table_image(report.image_urls)
        image_bytes = self._get_bytes(image_url)

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(image_bytes)
        return out_path

    def download_latest_asset_flows_image(
        self,
        output_path: str | Path,
    ) -> Path:
        full_table_path = self.download_latest_flow_table_image(output_path)
        self._crop_asset_flows_section(full_table_path)
        return full_table_path

    def build_asset_flows_sentence(
        self,
        *,
        mtd_flow_usd_m: float | None = None,
        leading_asset: str = "BTC",
    ) -> str:
        mtd_text = "***" if mtd_flow_usd_m is None else f"{mtd_flow_usd_m:,.0f}"
        return (
            "Exchange asset flow was positive over the past month at "
            f"USD{mtd_text}mm, led by {leading_asset}"
        )

    def get_latest_flow_table_image_url(self) -> str:
        report = self.get_latest_weekly_report()
        if not report.image_urls:
            raise RuntimeError(
                f"No images found for latest CoinShares report: {report.url}"
            )
        return self._select_flow_table_image(report.image_urls)

    def _get_text(self, endpoint: str) -> str:
        return self._get_bytes(endpoint).decode("utf-8", errors="replace")

    def _get_bytes(self, endpoint_or_url: str) -> bytes:
        url = (
            endpoint_or_url
            if endpoint_or_url.startswith(("http://", "https://"))
            else f"{self.base_url}{endpoint_or_url}"
        )
        req = urllib.request.Request(
            url=url,
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"CoinShares HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"CoinShares request failed: {exc.reason}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/rss+xml,text/html,image/*,*/*",
            "User-Agent": self.user_agent,
        }

    def _select_flow_table_image(self, image_urls: list[str]) -> str:
        candidates: list[tuple[int, int, str]] = []
        for image_url in image_urls:
            image_bytes = self._get_bytes(image_url)
            width, height = self._png_dimensions(image_bytes)
            candidates.append((width, height, image_url))

        tall_images = [
            candidate for candidate in candidates if candidate[1] > candidate[0]
        ]
        selected = max(tall_images or candidates, key=lambda candidate: candidate[1])
        return selected[2]

    @staticmethod
    def _extract_image_urls(content: str) -> list[str]:
        urls = re.findall(r'<img[^>]+src="([^"]+)"', unescape(content))
        return [url for url in urls if "medium.com/_/stat" not in url]

    @staticmethod
    def _parse_rss_date(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _png_dimensions(image_bytes: bytes) -> tuple[int, int]:
        if len(image_bytes) >= 24 and image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            width = int.from_bytes(image_bytes[16:20], "big")
            height = int.from_bytes(image_bytes[20:24], "big")
            return width, height
        return 0, 0

    @staticmethod
    def _crop_asset_flows_section(path: Path) -> None:
        with Image.open(path) as image:
            width, height = image.size
            top = int(height * 0.278)
            bottom = int(height * 0.622)
            cropped = image.crop((0, top, width, bottom))
            cropped.save(path)

    @staticmethod
    def _strip_query(url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _text(element: Any) -> str:
        return "" if element is None or element.text is None else element.text.strip()


if __name__ == "__main__":
    client = CoinSharesClient()

    sentence = client.build_asset_flows_sentence()
    print(sentence)

    client.download_latest_asset_flows_image(
        "results/market/coinshares_latest_asset_flows.png"
    )
