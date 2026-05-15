from __future__ import annotations

from pydantic import BaseModel

from src.clients.exchanges.binance import BinanceClient
from src.clients.exchanges.bybit import BybitClient
from src.clients.third_parties.coinmarketcap import CoinMarketCapClient
from src.utils.format_message import build_alt_market_summary_sentence


class AltMarketSummary(BaseModel):
    symbol: str
    spot_volume_24h: float | None
    binance_perp_volume_24h: float | None
    bybit_perp_volume_24h: float | None

    @property
    def sentence(self) -> str:
        return build_alt_market_summary_sentence(
            self.symbol,
            spot_volume_24h=self.spot_volume_24h,
            binance_perp_volume_24h=self.binance_perp_volume_24h,
            bybit_perp_volume_24h=self.bybit_perp_volume_24h,
        )


DEFAULT_COINMARKETCAP_SLUGS = {
    "ALT": "altlayer",
    "BB": "bouncebit",
    "ATA": "automata-network",
}


def get_alt_market_summary(
    symbol: str,
    *,
    coinmarketcap_slug: str | None = None,
    coinmarketcap_client: CoinMarketCapClient | None = None,
    binance_client: BinanceClient | None = None,
    bybit_client: BybitClient | None = None,
) -> AltMarketSummary:
    symbol = symbol.upper()
    cmc = coinmarketcap_client or CoinMarketCapClient()
    binance = binance_client or BinanceClient()
    bybit = bybit_client or BybitClient()
    cmc_slug = coinmarketcap_slug or DEFAULT_COINMARKETCAP_SLUGS.get(symbol)

    return AltMarketSummary(
        symbol=symbol,
        spot_volume_24h=_none_on_error(
            lambda: cmc.get_spot_volume_24h(
                symbol if cmc_slug is None else None,
                slug=cmc_slug,
            )
        ),
        binance_perp_volume_24h=_none_on_error(
            lambda: binance.get_usdt_perp_24h_quote_volume(symbol)
        ),
        bybit_perp_volume_24h=_none_on_error(
            lambda: bybit.get_usdt_perp_24h_turnover(symbol)
        ),
    )


def _none_on_error(fetch_value):
    try:
        return fetch_value()
    except Exception:
        return None


if __name__ == "__main__":
    for symbol in ["ALT", "BB", "ATA"]:
        summary = get_alt_market_summary(symbol)
        print(summary.sentence)
