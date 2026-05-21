from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.clients.exchanges.binance import BinanceClient
from src.clients.third_parties.coinank import CoinankClient
from src.clients.third_parties.coinshares import CoinSharesClient
from src.clients.third_parties.farside import FarsideClient
from src.scripts.alt_bb_ata.markdown_conversion import (
    markdown_to_pdf,
    markdown_to_word,
)
from src.scripts.alt_bb_ata.market_overview import (
    AltMarketSummary,
    get_alt_market_summary,
)
from src.scripts.alt_bb_ata.perp_market_analysis import (
    BinancePerpMarketAnalysis,
    build_binance_perp_market_analysis,
)
from src.scripts.alt_bb_ata.relative_performance import (
    build_relative_performance_sentence,
    relative_performance_to_png,
)
from src.scripts.alt_bb_ata.liquidity_table import build_liquidity_table_chart
from src.scripts.alt_bb_ata.aggregate_buy_sell_volume import (
    build_aggregate_buy_sell_volume_chart,
)
from src.scripts.alt_bb_ata.volume_per_exchange import (
    build_all_exchange_volume_charts,
)
from src.settings import app_settings
from src.utils.visualization import (
    coinank_long_short_realtime_to_png,
    coinank_open_interest_to_png,
    crypto_market_heatmap_to_png,
    etf_net_flows_to_png,
)

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("results/alt_bb_ata")
SUPPORTED_SYMBOLS = {"ALT", "BB", "ATA"}
REPORT_FILENAME = "report.md"
CRYPTO_HEATMAP_IMAGE = "crypto_heatmap.png"
ETF_NET_FLOWS_IMAGE = "etf_net_flows.png"
BTC_OPEN_INTEREST_IMAGE = "btc_open_interest.png"
COINSHARES_ASSET_FLOWS_IMAGE = "coinshares_asset_flows.png"
RELATIVE_PERFORMANCE_IMAGE = "relative_performance.png"
OPEN_INTEREST_IMAGE = "binance_perp_open_interest.png"
TAKER_BUY_SELL_IMAGE = "binance_perp_taker_buy_sell.png"
LIQUIDATIONS_IMAGE = "perp_liquidations.png"
LONG_SHORT_IMAGE = "perp_long_short.png"
SPOT_ORDER_BOOK_IMBALANCE_IMAGE = "spot_order_book_imbalance.png"
SPOT_ORDER_BOOK_LIQUIDITY_IMAGE = "spot_order_book_liquidity.png"
AGGREGATE_BUY_SELL_VOLUME_IMAGE = "aggregate_buy_sell_volume.png"
VOLUME_BY_EXCHANGE_IMAGE = "volume_by_exchange.png"
LIQUIDITY_TABLE_IMAGE = "liquidity_summary_table.png"
LIQUIDATIONS_SOURCE_URL = "https://www.coinglass.com/pro/futures/Liquidations"
LONG_SHORT_SOURCE_URL = "https://coinank.com/longshort/realtime"
SPOT_ORDER_BOOK_LIQUIDITY_SOURCE_URL = "https://www.coinglass.com/pro/depth-delta"


@dataclass(slots=True)
class MarketOverviewAssets:
    crypto_market_sentence: str
    etf_sentence: str
    btc_open_interest_sentence: str
    asset_flow_sentence: str


@dataclass(slots=True)
class LongShortAssets:
    image_path: Path | None
    sentence: str
    error: str | None = None


@dataclass(slots=True)
class AltMarkdownReport:
    symbol: str
    report_date: pd.Timestamp
    days: int
    markdown_path: Path
    content: str


def export_alt_markdown_report(
    report: AltMarkdownReport,
    *,
    output_format: str = "docx",
) -> Path:
    if output_format == "pdf":
        return markdown_to_pdf(report.markdown_path)
    if output_format == "docx":
        return markdown_to_word(report.markdown_path)
    raise ValueError(f"Unsupported export format: {output_format}")


def build_alt_markdown_report(
    symbol: str,
    *,
    report_date: str | pd.Timestamp | None = None,
    days: int = 14,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> AltMarkdownReport:
    base_asset = _base_asset(symbol)
    target_date = _resolve_report_date(report_date)
    report_dir = _report_dir(Path(output_dir), target_date, base_asset)
    report_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = report_dir / REPORT_FILENAME
    relative_chart_path = report_dir / RELATIVE_PERFORMANCE_IMAGE

    market_assets = _build_market_overview_assets(
        report_dir,
        report_date=target_date.strftime("%Y-%m-%d"),
        days=days,
    )
    market_summary, market_error = _try_market_summary(base_asset)
    relative_chart, relative_error = _try_relative_performance_chart(
        base_asset,
        relative_chart_path,
        days=days,
    )
    perp_analysis, perp_error = _try_perp_analysis(
        base_asset,
        report_date=target_date.strftime("%Y-%m-%d"),
        days=days,
        output_dir=report_dir,
    )
    perp_analysis = _normalize_perp_image_paths(perp_analysis, report_dir)
    long_short_assets = _try_long_short_realtime(
        base_asset,
        report_dir / LONG_SHORT_IMAGE,
    )
    liquidity_table_path, liquidity_table_error = _try_liquidity_table_chart(
        base_asset,
        report_date=target_date.strftime("%Y-%m-%d"),
        days=days,
        output_dir=report_dir,
    )
    aggregate_buy_sell_path, aggregate_buy_sell_error = (
        _try_aggregate_buy_sell_volume_chart(
            base_asset,
            report_date=target_date.strftime("%Y-%m-%d"),
            days=days,
            output_dir=report_dir,
        )
    )
    exchange_volume_paths, exchange_volume_errors = _try_exchange_volume_charts(
        base_asset,
        report_date=target_date.strftime("%Y-%m-%d"),
        days=days,
        output_dir=report_dir,
    )

    content = _render_markdown(
        symbol=base_asset,
        report_date=target_date,
        days=days,
        markdown_path=markdown_path,
        market_assets=market_assets,
        market_summary=market_summary,
        market_error=market_error,
        relative_chart_path=relative_chart or relative_chart_path,
        relative_error=relative_error,
        perp_analysis=perp_analysis,
        perp_error=perp_error,
        long_short_assets=long_short_assets,
        liquidity_table_path=liquidity_table_path,
        liquidity_table_error=liquidity_table_error,
        aggregate_buy_sell_path=aggregate_buy_sell_path,
        aggregate_buy_sell_error=aggregate_buy_sell_error,
        exchange_volume_paths=exchange_volume_paths,
        exchange_volume_errors=exchange_volume_errors,
    )
    markdown_path.write_text(content, encoding="utf-8")
    return AltMarkdownReport(
        symbol=base_asset,
        report_date=target_date,
        days=days,
        markdown_path=markdown_path,
        content=content,
    )


def _try_market_summary(symbol: str) -> tuple[AltMarketSummary | None, str | None]:
    try:
        return get_alt_market_summary(symbol), None
    except Exception as exc:
        logger.warning("Failed to build %s market summary.", symbol, exc_info=True)
        return None, str(exc)


def _build_market_overview_assets(
    report_dir: Path,
    *,
    report_date: str,
    days: int,
) -> MarketOverviewAssets:
    crypto_sentence = _try_crypto_market_overview(report_dir / CRYPTO_HEATMAP_IMAGE)
    etf_sentence = _try_etf_flows(
        report_dir / ETF_NET_FLOWS_IMAGE,
        report_date=report_date,
        days=days,
    )
    btc_open_interest_sentence = _try_btc_open_interest(
        report_dir / BTC_OPEN_INTEREST_IMAGE,
        report_date=report_date,
        days=days,
    )
    asset_flow_sentence = _try_coinshares_asset_flows(
        report_dir / COINSHARES_ASSET_FLOWS_IMAGE,
    )
    return MarketOverviewAssets(
        crypto_market_sentence=crypto_sentence,
        etf_sentence=etf_sentence,
        btc_open_interest_sentence=btc_open_interest_sentence,
        asset_flow_sentence=asset_flow_sentence,
    )


def _try_crypto_market_overview(output_path: Path) -> str:
    try:
        client = BinanceClient()
        summary = client.get_crypto_market_24h_summary()
        heatmap_df = client.get_usdt_market_heatmap_data(top_n=50)
        crypto_market_heatmap_to_png(heatmap_df, output_path, top_n=50)
        return summary.sentence
    except Exception as exc:
        logger.warning("Failed to build crypto market overview.", exc_info=True)
        return _placeholder_with_error(
            "Crypto market was *** over the past 24H, BTC was *** ***% on the day.",
            str(exc),
        )


def _try_etf_flows(output_path: Path, *, report_date: str, days: int) -> str:
    try:
        client = FarsideClient()
        flows = client.get_btc_eth_etf_net_flows(days=days, end_date=report_date)
        etf_net_flows_to_png(flows, output_path)
        btc_latest = flows["BTC"].iloc[-1]
        eth_latest = flows["ETH"].iloc[-1]
        flow_date = pd.Timestamp(btc_latest["date"]).strftime("%-d %B")
        return (
            f"BTC ETF flows were {_positive_negative(float(btc_latest['total']))} "
            f"at ${abs(float(btc_latest['total'])):,.1f}mm and ETH ETF flows were "
            f"{_positive_negative(float(eth_latest['total']))} at "
            f"${abs(float(eth_latest['total'])):,.1f}mm as on {flow_date}."
        )
    except Exception as exc:
        logger.warning("Failed to build ETF flows.", exc_info=True)
        return _placeholder_with_error(
            "BTC ETF flows were *** at $***mm and ETH ETF flows were *** at $***mm as on ***.",
            str(exc),
        )


def _try_btc_open_interest(output_path: Path, *, report_date: str, days: int) -> str:
    try:
        client = CoinankClient()
        df = client.get_open_interest_chart(base_asset="BTC")
        df = df[df["date"] <= pd.Timestamp(report_date).normalize()].tail(days)
        summary = client.get_open_interest_summary(
            base_asset="BTC", report_date=report_date
        )
        coinank_open_interest_to_png(df, output_path)
        return summary.sentence
    except Exception as exc:
        logger.warning("Failed to build BTC open interest.", exc_info=True)
        return _placeholder_with_error(
            "Overall BTC OI was *** at $***B on ***, as compared to the previous day",
            str(exc),
        )


def _try_coinshares_asset_flows(output_path: Path) -> str:
    try:
        client = CoinSharesClient()
        client.download_latest_asset_flows_image(output_path)
        return client.build_asset_flows_sentence()
    except Exception as exc:
        logger.warning("Failed to build CoinShares asset flows.", exc_info=True)
        return _placeholder_with_error(
            "Exchange asset flow was positive over the past month at USD***mm, led by BTC",
            str(exc),
        )


def _try_long_short_realtime(
    symbol: str,
    output_path: Path,
) -> LongShortAssets:
    try:
        client = CoinankClient()
        summary = client.get_long_short_realtime_summary(base_asset=symbol)
        coinank_long_short_realtime_to_png(summary, output_path)
        return LongShortAssets(
            image_path=output_path,
            sentence="Perp long position vs short position over recent period.",
        )
    except Exception as exc:
        logger.warning(
            "Failed to build %s long-short realtime snapshot.", symbol, exc_info=True
        )
        return LongShortAssets(
            image_path=None,
            sentence=_placeholder_with_error(
                "Perp long position vs short position over recent period.",
                str(exc),
            ),
            error=str(exc),
        )


def _try_relative_performance_chart(
    symbol: str,
    output_path: Path,
    *,
    days: int,
) -> tuple[Path | None, str | None]:
    try:
        return relative_performance_to_png(symbol, output_path, days=days), None
    except Exception as exc:
        logger.warning(
            "Failed to build %s relative performance chart.", symbol, exc_info=True
        )
        if output_path.exists():
            return output_path, str(exc)
        return None, str(exc)


def _try_perp_analysis(
    symbol: str,
    *,
    report_date: str,
    days: int,
    output_dir: Path,
) -> tuple[BinancePerpMarketAnalysis | None, str | None]:
    try:
        return (
            build_binance_perp_market_analysis(
                symbol,
                report_date=report_date,
                days=days,
                output_dir=output_dir,
            ),
            None,
        )
    except Exception as exc:
        logger.warning(
            "Failed to build %s perp market analysis.", symbol, exc_info=True
        )
        return None, str(exc)


def _try_liquidity_table_chart(
    symbol: str,
    *,
    report_date: str,
    days: int,
    output_dir: Path,
) -> tuple[Path | None, str | None]:
    try:
        chart = build_liquidity_table_chart(
            symbol,
            report_date=report_date,
            days=days,
            output_dir=output_dir,
        )
        return chart.output_path, None
    except Exception as exc:
        logger.warning(
            "Failed to build %s liquidity summary table.", symbol, exc_info=True
        )
        return None, str(exc)


def _try_aggregate_buy_sell_volume_chart(
    symbol: str,
    *,
    report_date: str,
    days: int,
    output_dir: Path,
) -> tuple[Path | None, str | None]:
    try:
        chart = build_aggregate_buy_sell_volume_chart(
            symbol,
            report_date=report_date,
            days=days,
            output_dir=output_dir,
        )
        return chart.output_path, None
    except Exception as exc:
        logger.warning(
            "Failed to build %s aggregate buy/sell chart.", symbol, exc_info=True
        )
        return None, str(exc)


def _try_exchange_volume_charts(
    symbol: str,
    *,
    report_date: str,
    days: int,
    output_dir: Path,
) -> tuple[list[Path], list[str]]:
    try:
        charts = build_all_exchange_volume_charts(
            symbol=symbol,
            report_date=report_date,
            days=days,
            output_dir=output_dir,
        )
        return [chart.output_path for chart in charts], []
    except Exception as exc:
        logger.warning(
            "Failed to build %s exchange-volume charts.", symbol, exc_info=True
        )
        return [], [str(exc)]


def _normalize_perp_image_paths(
    analysis: BinancePerpMarketAnalysis | None,
    report_dir: Path,
) -> BinancePerpMarketAnalysis | None:
    if analysis is None:
        return None

    open_interest_path = report_dir / OPEN_INTEREST_IMAGE
    taker_buy_sell_path = report_dir / TAKER_BUY_SELL_IMAGE
    liquidation_path = report_dir / LIQUIDATIONS_IMAGE
    _copy_if_different(analysis.open_interest_image_path, open_interest_path)
    _copy_if_different(analysis.taker_buy_sell_image_path, taker_buy_sell_path)
    _copy_if_different(analysis.liquidation_image_path, liquidation_path)

    return BinancePerpMarketAnalysis(
        symbol=analysis.symbol,
        open_interest=analysis.open_interest,
        taker_buy_sell=analysis.taker_buy_sell,
        liquidations=analysis.liquidations,
        open_interest_sentence=analysis.open_interest_sentence,
        taker_buy_sell_sentence=analysis.taker_buy_sell_sentence,
        liquidation_sentence=analysis.liquidation_sentence,
        open_interest_image_path=open_interest_path,
        taker_buy_sell_image_path=taker_buy_sell_path,
        liquidation_image_path=liquidation_path,
    )


def _copy_if_different(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve() or not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)


def _render_markdown(
    *,
    symbol: str,
    report_date: pd.Timestamp,
    days: int,
    markdown_path: Path,
    market_assets: MarketOverviewAssets,
    market_summary: AltMarketSummary | None,
    market_error: str | None,
    relative_chart_path: Path | None,
    relative_error: str | None,
    perp_analysis: BinancePerpMarketAnalysis | None,
    perp_error: str | None,
    long_short_assets: LongShortAssets,
    liquidity_table_path: Path | None,
    liquidity_table_error: str | None,
    aggregate_buy_sell_path: Path | None,
    aggregate_buy_sell_error: str | None,
    exchange_volume_paths: list[Path],
    exchange_volume_errors: list[str],
) -> str:
    report_date_text = report_date.strftime("%-d %b %Y")
    relative_sentence, relative_caption = build_relative_performance_sentence(
        symbol,
        days=min(days, 7),
    )

    lines = [
        f"# {symbol} Trading Report - {report_date_text}",
        "",
        "## <u>Section 1: Market overview</u>",
        "",
        f"- {market_assets.crypto_market_sentence}",
        "",
        _image_or_placeholder(
            markdown_path.parent / CRYPTO_HEATMAP_IMAGE,
            markdown_path=markdown_path,
            alt_text="Crypto market heatmap",
            fallback_filename=CRYPTO_HEATMAP_IMAGE,
        ),
        "",
        f"- {market_assets.etf_sentence}",
        "",
        _image_or_placeholder(
            markdown_path.parent / ETF_NET_FLOWS_IMAGE,
            markdown_path=markdown_path,
            alt_text="BTC and ETH ETF net flows",
            fallback_filename=ETF_NET_FLOWS_IMAGE,
        ),
        "",
        f"- {market_assets.btc_open_interest_sentence}",
        "",
        _image_or_placeholder(
            markdown_path.parent / BTC_OPEN_INTEREST_IMAGE,
            markdown_path=markdown_path,
            alt_text="BTC open interest",
            fallback_filename=BTC_OPEN_INTEREST_IMAGE,
        ),
        "",
        market_assets.asset_flow_sentence,
        "",
        _image_or_placeholder(
            markdown_path.parent / COINSHARES_ASSET_FLOWS_IMAGE,
            markdown_path=markdown_path,
            alt_text="CoinShares flows by asset",
            fallback_filename=COINSHARES_ASSET_FLOWS_IMAGE,
        ),
        "",
        f"## <u>Section 2: {symbol} Market Summary</u>",
        "",
        _market_summary_sentence(symbol, market_summary, market_error),
        "",
        "### <u>Relative performance</u>",
        "",
        f"- {relative_sentence}",
        f"- {relative_caption}",
        "",
        _image_or_placeholder(
            relative_chart_path,
            markdown_path=markdown_path,
            alt_text=f"{symbol} relative performance",
            fallback_filename=RELATIVE_PERFORMANCE_IMAGE,
            error=relative_error,
        ),
        "",
        "### <u>Perp market analysis</u>",
        "",
        (
            "Given that Binance perp trades more volume than all other perp and spot pairs, "
            "analysing Binance perp data provides valuable insight into the market."
        ),
        "",
        _perp_open_interest_block(perp_analysis, perp_error, markdown_path),
        "",
        _perp_taker_volume_block(perp_analysis, perp_error, markdown_path),
        "",
        _perp_liquidation_block(
            symbol,
            report_date,
            markdown_path,
            perp_analysis,
            perp_error,
        ),
        "",
        _perp_long_short_block(markdown_path, long_short_assets),
        "",
        "### <u>Spot order book insight: Book imbalance</u>",
        "",
        "- As a yardstick for volatility, we measure order book imbalance in the first 20 levels of the book = total $ value of offers / total $ value of bids",
        "- A high imbalance ratio implies more offers than bids; conversely a low imbalance ratio implies more bids than offers",
        "- The purpose behind measuring this is to give insight into the state of the order book and market; a temporary spike is not cause for concern; however, a high sustained imbalance may be something worth investigating",
        "- The order book imbalance levels were generally *** in the past 14 days.",
        "",
        _image_or_placeholder(
            None,
            markdown_path=markdown_path,
            alt_text="Spot order book imbalance",
            fallback_filename=SPOT_ORDER_BOOK_IMBALANCE_IMAGE,
        ),
        "",
        "### <u>Spot order book liquidity</u>",
        "",
        "- As another measure for liquidity, we look at ratio of bids to offers within +/-1% of the orderbook",
        "- There were *** bids than offers in the orderbook in the last week",
        "",
        _image_or_placeholder(
            None,
            markdown_path=markdown_path,
            alt_text="Spot order book liquidity",
            fallback_filename=SPOT_ORDER_BOOK_LIQUIDITY_IMAGE,
        ),
        "",
        SPOT_ORDER_BOOK_LIQUIDITY_SOURCE_URL,
        "",
        "## <u>Section 3: Trade Performance</u>",
        "",
        "Our goal has been to provide sufficient liquidity across all major exchanges and pairs to facilitate stable markets in all conditions. Below is a summary of market liquidity our trade performance.",
        "",
        "The section below goes through our trade performance over the past week, including aggregate buys and sells as well as trade volume and market share by exchange and trading pair.",
        "",
        _image_or_placeholder(
            liquidity_table_path,
            markdown_path=markdown_path,
            alt_text="Liquidity summary table",
            fallback_filename=LIQUIDITY_TABLE_IMAGE,
            error=liquidity_table_error,
        ),
        "",
        "- Aggregate buy/sell volume across all exchanges",
        "",
        _image_or_placeholder(
            aggregate_buy_sell_path,
            markdown_path=markdown_path,
            alt_text="Aggregate buy sell volume",
            fallback_filename=AGGREGATE_BUY_SELL_VOLUME_IMAGE,
            error=aggregate_buy_sell_error,
        ),
        "",
        "- Volume by exchange",
        "",
    ]
    if exchange_volume_paths:
        for index, image_path in enumerate(exchange_volume_paths):
            lines.extend(
                [
                    _image_or_placeholder(
                        image_path,
                        markdown_path=markdown_path,
                        alt_text=f"Volume by exchange {index + 1}",
                        fallback_filename=image_path.name,
                    ),
                    "",
                ]
            )
    else:
        lines.extend(
            [
                _image_or_placeholder(
                    None,
                    markdown_path=markdown_path,
                    alt_text="Volume by exchange",
                    fallback_filename=VOLUME_BY_EXCHANGE_IMAGE,
                    error="; ".join(exchange_volume_errors)
                    if exchange_volume_errors
                    else None,
                ),
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _market_summary_sentence(
    symbol: str,
    summary: AltMarketSummary | None,
    error: str | None,
) -> str:
    if summary is not None:
        return summary.sentence
    if error:
        return (
            f"In the past 24H, {symbol} traded average spot volume of ~***mm. "
            "Binance perp recorded trading volume of ~***mm and Bybit perp ~***mm "
            f"over the past 24H. <!-- data unavailable: {error} -->"
        )
    return (
        f"In the past 24H, {symbol} traded average spot volume of ~***mm. "
        "Binance perp recorded trading volume of ~***mm and Bybit perp ~***mm "
        "over the past 24H."
    )


def _perp_open_interest_block(
    analysis: BinancePerpMarketAnalysis | None,
    error: str | None,
    markdown_path: Path,
) -> str:
    if analysis is None:
        return "\n\n".join(
            [
                _image_or_placeholder(
                    None,
                    markdown_path=markdown_path,
                    alt_text="Binance perp open interest",
                    fallback_filename=OPEN_INTEREST_IMAGE,
                ),
                _placeholder_with_error(
                    "Open Interest was *** by ~***m on *** compared to previous day.",
                    error,
                ),
            ]
        )

    return "\n\n".join(
        [
            _image_or_placeholder(
                analysis.open_interest_image_path,
                markdown_path=markdown_path,
                alt_text=f"{analysis.symbol} Binance perp open interest",
                fallback_filename=OPEN_INTEREST_IMAGE,
            ),
            analysis.open_interest_sentence,
        ]
    )


def _perp_taker_volume_block(
    analysis: BinancePerpMarketAnalysis | None,
    error: str | None,
    markdown_path: Path,
) -> str:
    if analysis is None:
        return "\n\n".join(
            [
                _image_or_placeholder(
                    None,
                    markdown_path=markdown_path,
                    alt_text="Binance perp taker buy sell volume",
                    fallback_filename=TAKER_BUY_SELL_IMAGE,
                ),
                _placeholder_with_error(
                    "Perp *** volume outpaced *** volume by ***m on ***.",
                    error,
                ),
            ]
        )

    return "\n\n".join(
        [
            _image_or_placeholder(
                analysis.taker_buy_sell_image_path,
                markdown_path=markdown_path,
                alt_text=f"{analysis.symbol} Binance perp taker buy sell volume",
                fallback_filename=TAKER_BUY_SELL_IMAGE,
            ),
            analysis.taker_buy_sell_sentence,
        ]
    )


def _perp_liquidation_block(
    symbol: str,
    report_date: pd.Timestamp,
    markdown_path: Path,
    analysis: BinancePerpMarketAnalysis | None,
    error: str | None,
) -> str:
    if analysis is not None:
        return "\n\n".join(
            [
                _image_or_placeholder(
                    analysis.liquidation_image_path,
                    markdown_path=markdown_path,
                    alt_text=f"{symbol} perp liquidations",
                    fallback_filename=LIQUIDATIONS_IMAGE,
                    error=error,
                ),
                analysis.liquidation_sentence,
            ]
        )
    date_text = report_date.strftime("%-d %B")
    return "\n\n".join(
        [
            _image_or_placeholder(
                None,
                markdown_path=markdown_path,
                alt_text=f"{symbol} perp liquidations",
                fallback_filename=LIQUIDATIONS_IMAGE,
            ),
            LIQUIDATIONS_SOURCE_URL,
            (
                f"Perp liquidations *** over the past 24H at ~*** longs and "
                f"~*** shorts liquidated as on {date_text}."
            ),
        ]
    )


def _perp_long_short_block(
    markdown_path: Path,
    assets: LongShortAssets,
) -> str:
    if assets.image_path is not None:
        return "\n\n".join(
            [
                _image_or_placeholder(
                    assets.image_path,
                    markdown_path=markdown_path,
                    alt_text="Perp long short positioning",
                    fallback_filename=LONG_SHORT_IMAGE,
                    error=assets.error,
                ),
                assets.sentence,
            ]
        )
    return "\n\n".join(
        [
            _image_or_placeholder(
                None,
                markdown_path=markdown_path,
                alt_text="Perp long short positioning",
                fallback_filename=LONG_SHORT_IMAGE,
            ),
            LONG_SHORT_SOURCE_URL,
            assets.sentence,
        ]
    )


def _image_or_placeholder(
    path: Path | None,
    *,
    markdown_path: Path,
    alt_text: str,
    fallback_filename: str,
    error: str | None = None,
) -> str:
    image_path = path if path is not None else markdown_path.parent / fallback_filename
    image_ref = _relative_image_ref(image_path, markdown_path)
    image_markdown = f"![{alt_text}]({image_ref})"
    if path is not None and path.exists() and error:
        return _placeholder_with_error(image_markdown, error)
    return image_markdown


def _relative_image_ref(path: Path, markdown_path: Path) -> str:
    resolved_path = Path(path).resolve()
    resolved_base = markdown_path.parent.resolve()
    if _is_relative_to(resolved_path, resolved_base):
        return resolved_path.relative_to(resolved_base).as_posix()
    return resolved_path.as_posix()


def _placeholder_with_error(text: str, error: str | None) -> str:
    if not error:
        return text
    cleaned_error = " ".join(str(error).split())
    return f"{text} <!-- data unavailable: {cleaned_error} -->"


def _resolve_report_date(report_date: str | pd.Timestamp | None) -> pd.Timestamp:
    if report_date is None:
        target = pd.Timestamp.now(tz=app_settings.tz)
    else:
        target = pd.Timestamp(report_date)
        if target.tzinfo is None:
            target = target.tz_localize(app_settings.tz)
        else:
            target = target.tz_convert(app_settings.tz)
    return target.normalize()


def _base_asset(symbol: str) -> str:
    normalized = symbol.upper()
    return normalized[:-4] if normalized.endswith("USDT") else normalized


def _positive_negative(value: float) -> str:
    return "positive" if value >= 0 else "negative"


def _report_dir(output_dir: Path, report_date: pd.Timestamp, symbol: str) -> Path:
    return output_dir / report_date.strftime("%Y-%m-%d") / symbol.upper()


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an ALT/BB/ATA report and export it to Word or PDF."
    )
    parser.add_argument(
        "symbol", choices=sorted(SUPPORTED_SYMBOLS), help="Report symbol."
    )
    parser.add_argument(
        "--report-date",
        default=None,
        help="Report date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Trailing period used for charts. Defaults to 14.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for the markdown report and generated charts.",
    )
    parser.add_argument(
        "--format",
        choices=("docx", "pdf"),
        default="docx",
        help="Export format. Defaults to docx.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    report = build_alt_markdown_report(
        args.symbol,
        report_date=args.report_date,
        days=args.days,
        output_dir=args.output_dir,
    )
    export_path = export_alt_markdown_report(report, output_format=args.format)
    print(export_path)


if __name__ == "__main__":
    main()
