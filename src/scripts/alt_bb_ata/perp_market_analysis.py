from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.clients.binance import BinanceClient
from src.utils.visualization import (
    binance_perp_open_interest_to_png,
    binance_perp_taker_buy_sell_to_png,
)


@dataclass(slots=True)
class BinancePerpMarketAnalysis:
    symbol: str
    open_interest: pd.DataFrame
    taker_buy_sell: pd.DataFrame
    open_interest_sentence: str
    taker_buy_sell_sentence: str
    open_interest_image_path: Path
    taker_buy_sell_image_path: Path


def build_binance_perp_market_analysis(
    symbol: str,
    *,
    report_date: str | pd.Timestamp | None = None,
    days: int = 30,
    output_dir: str | Path = "results/market",
    binance_client: BinanceClient | None = None,
) -> BinancePerpMarketAnalysis:
    base_asset = _base_asset(symbol)
    client = binance_client or BinanceClient()
    start_time_ms, end_time_ms = _time_window_ms(report_date, days=days)

    open_interest = client.get_futures_open_interest_history(
        base_asset,
        period="1d",
        limit=min(max(days + 2, 2), 500),
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
    )
    taker_buy_sell = client.get_futures_taker_buy_sell_volume(
        base_asset,
        period="1d",
        limit=min(max(days + 2, 2), 500),
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
    )

    output_base = Path(output_dir)
    open_interest_image_path = (
        output_base / f"{base_asset.lower()}_binance_perp_open_interest.png"
    )
    taker_buy_sell_image_path = (
        output_base / f"{base_asset.lower()}_binance_perp_taker_buy_sell.png"
    )

    binance_perp_open_interest_to_png(
        open_interest,
        open_interest_image_path,
        base_asset=base_asset,
        days=days,
    )
    binance_perp_taker_buy_sell_to_png(
        taker_buy_sell,
        taker_buy_sell_image_path,
        base_asset=base_asset,
        days=days,
    )

    return BinancePerpMarketAnalysis(
        symbol=base_asset,
        open_interest=open_interest,
        taker_buy_sell=taker_buy_sell,
        open_interest_sentence=build_open_interest_sentence(
            open_interest,
            base_asset=base_asset,
            report_date=report_date,
        ),
        taker_buy_sell_sentence=build_taker_buy_sell_sentence(
            taker_buy_sell,
            base_asset=base_asset,
            report_date=report_date,
        ),
        open_interest_image_path=open_interest_image_path,
        taker_buy_sell_image_path=taker_buy_sell_image_path,
    )


def build_open_interest_sentence(
    df: pd.DataFrame,
    *,
    base_asset: str,
    report_date: str | pd.Timestamp | None = None,
) -> str:
    row, previous_row = _row_and_previous(df, report_date=report_date)
    change = float(row["open_interest"]) - float(previous_row["open_interest"])
    direction = "up" if change > 0 else "down"
    return (
        f"Open Interest was {direction} by ~{abs(change) / 1_000_000:.1f}m "
        f"on {_format_report_date(row['date'])} compared to previous day."
    )


def build_taker_buy_sell_sentence(
    df: pd.DataFrame,
    *,
    base_asset: str,
    report_date: str | pd.Timestamp | None = None,
) -> str:
    row, _ = _row_and_previous(df, report_date=report_date)
    buy_volume = float(row["buy_volume"])
    sell_volume = float(row["sell_volume"])
    if buy_volume >= sell_volume:
        leader = "Buy"
        follower = "Sell"
        difference = buy_volume - sell_volume
    else:
        leader = "Sell"
        follower = "Buy"
        difference = sell_volume - buy_volume

    return (
        f"Perp {leader} volume outpaced {follower} volume by "
        f"{difference / 1_000_000:.1f}m {base_asset.upper()} "
        f"on {_format_report_date(row['date'])}."
    )


def _row_and_previous(
    df: pd.DataFrame,
    *,
    report_date: str | pd.Timestamp | None,
) -> tuple[pd.Series, pd.Series]:
    if df.empty:
        raise ValueError("Binance perp data is empty.")

    plot_df = df.sort_values(by="date").reset_index(drop=True)
    if report_date is None:
        row_index = len(plot_df) - 1
    else:
        target = pd.Timestamp(report_date)
        if target.tzinfo is None:
            target = target.tz_localize("UTC")
        else:
            target = target.tz_convert("UTC")
        target_date = target.date()
        matches = plot_df.index[plot_df["date"].dt.date == target_date].tolist()
        if not matches:
            raise ValueError(f"No Binance perp data found for {target_date}.")
        row_index = matches[-1]

    if row_index <= 0:
        raise ValueError("Need at least one previous day to build the summary.")
    return plot_df.iloc[row_index], plot_df.iloc[row_index - 1]


def _time_window_ms(
    report_date: str | pd.Timestamp | None,
    *,
    days: int,
) -> tuple[int | None, int | None]:
    if report_date is None:
        report_date = pd.Timestamp.utcnow().normalize()

    target = pd.Timestamp(report_date)
    if target.tzinfo is None:
        target = target.tz_localize("UTC")
    else:
        target = target.tz_convert("UTC")
    # Binance futures data endpoints treat daily endTime as a publication cutoff,
    # so include one extra day and select the requested date locally.
    end = target.normalize() + pd.Timedelta(days=2) - pd.Timedelta(milliseconds=1)
    return None, int(end.timestamp() * 1000)


def _base_asset(symbol: str) -> str:
    normalized = symbol.upper()
    return normalized[:-4] if normalized.endswith("USDT") else normalized


def _format_report_date(value: str | pd.Timestamp) -> str:
    timestamp = pd.Timestamp(value)
    return f"{timestamp.day} {timestamp.strftime('%B')}"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Render Binance perp market analysis charts."
    )
    parser.add_argument(
        "symbol", nargs="?", default="ALT", help="Base asset, e.g. ALT, BB, ATA."
    )
    parser.add_argument(
        "--report-date", default=None, help="Report date in YYYY-MM-DD format."
    )
    parser.add_argument("--days", type=int, default=14, help="Trailing days to plot.")
    parser.add_argument(
        "--output-dir", default="results/market", help="Output directory."
    )
    args = parser.parse_args()

    analysis = build_binance_perp_market_analysis(
        args.symbol,
        report_date=args.report_date,
        days=args.days,
        output_dir=args.output_dir,
    )
    print(analysis.open_interest_sentence)
    print(analysis.taker_buy_sell_sentence)
    print(analysis.open_interest_image_path)
    print(analysis.taker_buy_sell_image_path)


if __name__ == "__main__":
    main()
