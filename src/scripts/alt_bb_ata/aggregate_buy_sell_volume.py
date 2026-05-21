from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

from src.clients.databases.influxdb import InfluxDBClient
from src.clients.exchanges.binance import BinanceClient
from src.scripts.alt_bb_ata.report_config import load_alt_report_section

DEFAULT_OUTPUT_DIR = Path("results/alt_bb_ata")
DEFAULT_IMAGE_NAME = "aggregate_buy_sell_volume.png"
DEFAULT_TIMEZONE = "UTC"
SUPPORTED_SYMBOLS = {"ALT"}
BUY_COLOR = "#59b45a"
SELL_COLOR = "#f06a78"
GRID_COLOR = "#d2d8df"


@dataclass(slots=True)
class AggregateBuySellVolumeChart:
    symbol: str
    days: int
    output_path: Path
    volume_data: pd.DataFrame
    price_data: pd.DataFrame


def build_aggregate_buy_sell_volume_chart(
    symbol: str,
    *,
    report_date: str | pd.Timestamp | None = None,
    days: int = 14,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    timezone: str = DEFAULT_TIMEZONE,
    influxdb_client: InfluxDBClient | None = None,
    binance_client: BinanceClient | None = None,
) -> AggregateBuySellVolumeChart:
    base_asset = _base_asset(symbol)
    config = _load_symbol_config(base_asset)
    client = influxdb_client or InfluxDBClient()
    price_client = binance_client or BinanceClient()
    data_report_date = _effective_data_report_date(report_date)

    volume_df = client.get_trade_buy_sell_amount_history(
        list(config["trade_measurements"]),
        days=days,
        report_date=data_report_date,
        timezone=timezone,
    )
    if volume_df.empty:
        raise ValueError(f"No trade buy/sell data found for {base_asset}.")

    chart_volume_df = _normalize_buy_sell_history(
        volume_df,
        report_date=data_report_date,
        days=days,
    )
    price_df = _load_price_data(
        price_client,
        str(config["price_symbol"]),
        report_date=data_report_date,
        days=days,
    )
    output_path = _resolve_output_path(Path(output_dir), base_asset, report_date)
    aggregate_buy_sell_volume_to_png(
        chart_volume_df,
        price_df,
        output_path,
        base_asset=base_asset,
    )
    return AggregateBuySellVolumeChart(
        symbol=base_asset,
        days=days,
        output_path=output_path,
        volume_data=chart_volume_df,
        price_data=price_df,
    )


def aggregate_buy_sell_volume_to_png(
    volume_df: pd.DataFrame,
    price_df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str,
    figsize: tuple[float, float] = (14, 6.7),
    dpi: int = 180,
) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    plot_volume = volume_df.copy().sort_values(by="date").reset_index(drop=True)
    plot_price = price_df.copy().sort_values(by="date").reset_index(drop=True)
    if plot_volume.empty or plot_price.empty:
        raise ValueError("Volume or price data is empty.")

    plot_price = plot_price[plot_price["date"].isin(plot_volume["date"])].reset_index(
        drop=True
    )
    if plot_price.empty:
        raise ValueError("No overlapping price data found for the requested period.")

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.0], hspace=0.16)
    ax_bar = fig.add_subplot(gs[0, 0])
    ax_price = fig.add_subplot(gs[1, 0])
    ax_volume = ax_price.twinx()

    fig.patch.set_facecolor("white")
    for axis in [ax_bar, ax_price, ax_volume]:
        axis.set_facecolor("white")

    x = np.arange(len(plot_volume))
    width = 0.36
    buy_values = plot_volume["buy"].astype(float)
    sell_values = plot_volume["sell"].astype(float)
    buy_bars = ax_bar.bar(
        x - width / 2,
        buy_values,
        width=width,
        color=BUY_COLOR,
        edgecolor=BUY_COLOR,
        zorder=3,
        label="Buy",
    )
    sell_bars = ax_bar.bar(
        x + width / 2,
        sell_values,
        width=width,
        color=SELL_COLOR,
        edgecolor=SELL_COLOR,
        zorder=3,
        label="Sell",
    )

    ax_bar.text(
        0.0,
        1.02,
        f"Aggregate Buy / Sell {base_asset}",
        transform=ax_bar.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color="#333333",
        fontweight="bold",
    )
    ax_bar.legend(
        loc="upper right",
        frameon=False,
        fontsize=8,
        ncol=2,
        handlelength=1.0,
        columnspacing=0.8,
    )
    ax_bar.grid(
        True, axis="y", linestyle="-", linewidth=0.6, alpha=0.22, color=GRID_COLOR
    )
    ax_bar.grid(False, axis="x")
    ax_bar.tick_params(axis="x", colors="#67727d", labelsize=8, length=0)
    ax_bar.tick_params(axis="y", colors="#67727d", labelsize=8, length=0)
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels([d.strftime("%m/%d 00:00") for d in plot_volume["date"]])
    ax_bar.set_yticklabels([])

    max_bar_value = float(max(buy_values.max(), sell_values.max()))
    for bars in [buy_bars, sell_bars]:
        for bar in bars:
            height = float(bar.get_height())
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2,
                height + max_bar_value * 0.01,
                f"{int(round(height))}",
                ha="center",
                va="bottom",
                fontsize=5,
                color="#777777",
            )

    for spine in ax_bar.spines.values():
        spine.set_visible(False)

    candle_x = mdates.date2num(plot_price["date"].dt.to_pydatetime())  # pyrefly: ignore
    candle_width = 0.62
    for x_value, row in zip(candle_x, plot_price.itertuples(index=False), strict=False):
        open_price = float(row.open)
        high_price = float(row.high)
        low_price = float(row.low)
        close_price = float(row.close)
        color = BUY_COLOR if close_price >= open_price else "#ff0040"
        ax_price.vlines(
            x_value, low_price, high_price, color=color, linewidth=1.0, zorder=4
        )
        ax_price.add_patch(
            Rectangle(
                (x_value - candle_width / 2, min(open_price, close_price)),
                candle_width,
                max(abs(close_price - open_price), 1e-12),
                facecolor=color,
                edgecolor=color,
                linewidth=0.7,
                zorder=5,
            )
        )

    volume_colors = [
        BUY_COLOR if close_price >= open_price else SELL_COLOR
        for open_price, close_price in zip(
            plot_price["open"], plot_price["close"], strict=False
        )
    ]
    ax_volume.bar(
        plot_price["date"],
        plot_price["volume"].astype(float),
        color=volume_colors,
        width=0.62,
        alpha=0.28,
        zorder=1,
    )
    ax_price.text(
        0.01,
        0.06,
        "Binance spot volume",
        transform=ax_price.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color="#8a95a1",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.5},
        zorder=6,
    )

    ax_price.grid(
        True, axis="both", linestyle="-", linewidth=0.6, alpha=0.22, color=GRID_COLOR
    )
    ax_price.tick_params(axis="x", colors="#67727d", labelsize=8, length=0)
    ax_price.tick_params(axis="y", colors="#67727d", labelsize=8, length=0)
    ax_volume.tick_params(axis="y", length=0, labelleft=False, labelright=False)
    ax_price.set_ylabel("")
    ax_price.set_xlabel("")
    ax_volume.set_ylabel("")
    ax_price.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d 00:00"))

    price_min = float(plot_price["low"].min())
    price_max = float(plot_price["high"].max())
    price_padding = max((price_max - price_min) * 0.18, price_max * 0.01)
    ax_price.set_ylim(max(0, price_min - price_padding), price_max + price_padding)
    # Keep the public-volume bars visible without overpowering the candlesticks.
    ax_volume.set_ylim(0, float(plot_price["volume"].max()) * 2.2)

    for spine in ax_price.spines.values():
        spine.set_visible(False)
    for spine in ax_volume.spines.values():
        spine.set_visible(False)

    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.08, top=0.95, hspace=0.2)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def _load_symbol_config(symbol: str) -> dict[str, object]:
    config = load_alt_report_section(symbol, "aggregate_buy_sell_volume")
    if not isinstance(config, dict):
        raise ValueError(f"No aggregate buy/sell configuration found for {symbol}.")
    return config


def _normalize_buy_sell_history(
    volume_df: pd.DataFrame,
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> pd.DataFrame:
    start_date, end_date = _window_dates(report_date=report_date, days=days)
    date_index = pd.date_range(start_date, end_date, freq="D")
    pivot_df = (
        volume_df.pivot_table(
            index="date",
            columns="side",
            values="amount",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reindex(date_index, fill_value=0.0)
        .rename_axis("date")
        .reset_index()
    )
    for col in ["buy", "sell"]:
        if col not in pivot_df.columns:
            pivot_df[col] = 0.0
    return pivot_df.loc[:, ["date", "buy", "sell"]]


def _load_price_data(
    client: BinanceClient,
    price_symbol: str,
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> pd.DataFrame:
    start_date, end_date = _window_dates(report_date=report_date, days=days)
    start_time_ms, end_time_ms = _time_window_ms(report_date, days=days)
    klines = client.get_klines(
        price_symbol,
        interval="1d",
        limit=min(max(days + 2, 2), 1000),
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
    )
    rows = [
        {
            "date": pd.to_datetime(kline.open_time_ms, unit="ms", utc=True)
            .floor("D")
            .tz_localize(None),
            "open": kline.open_price,
            "high": kline.high_price,
            "low": kline.low_price,
            "close": kline.close_price,
            "volume": kline.volume,
        }
        for kline in klines
    ]
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    if df.empty:
        raise ValueError(f"No Binance kline data found for {price_symbol}.")
    window_df = df.sort_values(by="date")
    window_df = window_df[
        (window_df["date"] >= start_date) & (window_df["date"] <= end_date)
    ]
    return window_df.reset_index(drop=True)


def _window_dates(
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_date = _resolve_utc_report_date(report_date)
    start_date = end_date - pd.Timedelta(days=days - 1)
    return start_date.tz_localize(None), end_date.tz_localize(None)


def _effective_data_report_date(
    report_date: str | pd.Timestamp | None,
) -> pd.Timestamp:
    return _resolve_utc_report_date(report_date) - pd.Timedelta(days=1)


def _resolve_utc_report_date(
    report_date: str | pd.Timestamp | None,
) -> pd.Timestamp:
    if report_date is None:
        return pd.Timestamp.now(tz="UTC").normalize()

    target_date = pd.Timestamp(report_date)
    if target_date.tzinfo is None:
        target_date = target_date.tz_localize("UTC")
    else:
        target_date = target_date.tz_convert("UTC")
    return target_date.normalize()


def _time_window_ms(
    report_date: str | pd.Timestamp | None,
    *,
    days: int,
) -> tuple[int | None, int | None]:
    start_date, end_date = _window_dates(report_date=report_date, days=days)
    start_ts = pd.Timestamp(start_date).tz_localize("UTC")
    stop_ts = pd.Timestamp(end_date).tz_localize("UTC") + pd.Timedelta(days=1)
    return int(start_ts.timestamp() * 1000), int(stop_ts.timestamp() * 1000)


def _base_asset(symbol: str) -> str:
    normalized = symbol.upper()
    return normalized[:-4] if normalized.endswith("USDT") else normalized


def _resolve_output_path(
    output_dir: Path,
    symbol: str,
    report_date: str | pd.Timestamp | None,
) -> Path:
    _ = symbol
    _ = report_date
    return output_dir / DEFAULT_IMAGE_NAME


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render aggregate buy/sell amount and K-line chart."
    )
    parser.add_argument("symbol", nargs="?", default="ALT", help="Base asset.")
    parser.add_argument("--report-date", default=None, help="Optional YYYY-MM-DD.")
    parser.add_argument("--days", type=int, default=14, help="Trailing days.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory.",
    )
    args = parser.parse_args()

    symbol = args.symbol.upper()
    if symbol not in SUPPORTED_SYMBOLS:
        raise ValueError(
            f"Unsupported symbol '{symbol}'. Expected one of: {', '.join(sorted(SUPPORTED_SYMBOLS))}."
        )

    chart = build_aggregate_buy_sell_volume_chart(
        symbol,
        report_date=args.report_date,
        days=args.days,
        output_dir=args.output_dir,
    )
    print(chart.output_path)


if __name__ == "__main__":
    main()
