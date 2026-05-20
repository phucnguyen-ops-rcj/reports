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

DEFAULT_OUTPUT_DIR = Path("results/alt_bb_ata")
DEFAULT_IMAGE_NAME = "aggregate_buy_sell_volume.png"
SUPPORTED_SYMBOLS = {"ALT", "BB", "ATA"}
DEFAULT_TIMEZONE = "UTC"
BAR_COLOR = "#59b45a"
GRID_COLOR = "#d2d8df"
OHLCV_MEASUREMENTS = {
    "ALT": [
        "binance_ALTUSDT_ohlcv",
        "binance_ALTUSDC_ohlcv",
        "bybit_ALTUSDT_ohlcv",
        "gateio_ALT_USDT_ohlcv",
        "kucoin_KALT-USDT_ohlcv",
    ],
    "BB": [
        "gateio_BB_USDT_ohlcv",
        "kucoin_BB-USDT_ohlcv",
        "bybit_BBUSDT_ohlcv",
        "binance_BBUSDT_ohlcv",
    ],
    "ATA": [
        "kucoin_ATA-USDT_ohlcv",
        "gateio_ATA_USDT_ohlcv",
        "binance_ATAUSDT_ohlcv",
    ],
}


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
) -> AggregateBuySellVolumeChart:
    base_asset = _base_asset(symbol)
    client = influxdb_client or InfluxDBClient()
    measurement_names = OHLCV_MEASUREMENTS.get(base_asset, [])
    if not measurement_names:
        raise ValueError(f"No OHLCV measurements configured for {base_asset}.")

    volume_df = client.get_aggregate_ohlcv_volume_history(
        measurement_names,
        days=days,
        report_date=report_date,
        timezone=timezone,
    )
    if volume_df.empty:
        raise ValueError(f"No OHLCV volume data found for {base_asset}.")

    price_df = _load_price_data(
        client,
        base_asset,
        report_date=report_date,
        days=days,
        timezone=timezone,
    )
    output_path = _resolve_output_path(Path(output_dir), base_asset, report_date)
    aggregate_buy_sell_volume_to_png(
        volume_df,
        price_df,
        output_path,
        base_asset=base_asset,
        days=days,
        timezone=timezone,
    )
    return AggregateBuySellVolumeChart(
        symbol=base_asset,
        days=days,
        output_path=output_path,
        volume_data=volume_df,
        price_data=price_df,
    )


def aggregate_buy_sell_volume_to_png(
    volume_df: pd.DataFrame,
    price_df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str,
    days: int,
    timezone: str,
    figsize: tuple[float, float] = (14, 8),
    dpi: int = 180,
) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    plot_volume = (
        volume_df.copy().sort_values(by="date").tail(days).reset_index(drop=True)
    )
    plot_price = (
        price_df.copy().sort_values(by="date").tail(days).reset_index(drop=True)
    )
    if plot_volume.empty or plot_price.empty:
        raise ValueError("Volume or price data is empty.")

    merged_dates = plot_volume["date"]
    plot_price = plot_price[plot_price["date"].isin(merged_dates)].reset_index(
        drop=True
    )
    if plot_price.empty:
        raise ValueError("No overlapping price data found for the requested period.")

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.08, 1.0], hspace=0.18)
    ax_bar = fig.add_subplot(gs[0, 0])
    ax_price = fig.add_subplot(gs[1, 0])
    ax_volume = ax_price.twinx()

    fig.patch.set_facecolor("white")
    for axis in [ax_bar, ax_price, ax_volume]:
        axis.set_facecolor("white")

    fig.text(
        0.03,
        0.96,
        "I.",
        ha="left",
        va="top",
        fontsize=15,
        fontweight="bold",
        color="#111111",
    )
    fig.text(
        0.085,
        0.96,
        "Aggregate trade volume across all exchanges",
        ha="left",
        va="top",
        fontsize=16,
        fontweight="bold",
        color="#111111",
    )

    plot_start = plot_volume["date"].min().strftime("%-d %B")
    plot_end = plot_volume["date"].max().strftime("%-d %B")
    fig.text(
        0.03,
        0.885,
        f"Volume per exchange [1 of 1]  {days} days window  {plot_start} - {plot_end} / {timezone} 00:00-00:00",
        ha="left",
        va="top",
        fontsize=11,
        color="#333333",
    )
    fig.add_artist(
        plt.Line2D(
            [0.03, 0.71],
            [0.865, 0.865],
            transform=fig.transFigure,
            color="#777777",
            linewidth=0.8,
        )
    )
    fig.text(
        0.03,
        0.83,
        "Aggregated trade volume – 24 hr interval",
        ha="left",
        va="center",
        fontsize=16,
        color="#111111",
    )

    x = np.arange(len(plot_volume))
    volumes = plot_volume["volume"].astype(float)
    bars = ax_bar.bar(
        x,
        volumes,
        width=0.92,
        color=BAR_COLOR,
        edgecolor=BAR_COLOR,
        zorder=3,
    )

    ax_bar.text(
        0.0,
        0.98,
        f"Aggregate Volume {base_asset}",
        transform=ax_bar.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color="#333333",
        fontweight="bold",
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

    max_bar_value = float(volumes.max())
    for bar, value in zip(bars, volumes, strict=False):
        ax_bar.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_bar_value * 0.01,
            f"{int(round(value))}",
            ha="center",
            va="bottom",
            fontsize=5,
            color="#777777",
        )

    for spine in ax_bar.spines.values():
        spine.set_visible(False)

    fig.text(
        0.03,
        0.445,
        "Price - K-Line for the same time period",
        ha="left",
        va="center",
        fontsize=16,
        color="#111111",
    )

    candle_x = mdates.date2num(plot_price["date"].dt.to_pydatetime())  # pyrefly: ignore
    candle_width = 0.62
    for x_value, row in zip(candle_x, plot_price.itertuples(index=False), strict=False):
        open_price = float(row.open)
        high_price = float(row.high)
        low_price = float(row.low)
        close_price = float(row.close)
        color = BAR_COLOR if close_price >= open_price else "#ff0040"
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
        BAR_COLOR if close_price >= open_price else "#ff5b73"
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
    ax_volume.set_ylim(0, float(plot_price["volume"].max()) * 5.0)

    for spine in ax_price.spines.values():
        spine.set_visible(False)
    for spine in ax_volume.spines.values():
        spine.set_visible(False)

    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.08, top=0.86, hspace=0.2)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def _load_price_data(
    client: InfluxDBClient,
    symbol: str,
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
    timezone: str,
) -> pd.DataFrame:
    for measurement_name in OHLCV_MEASUREMENTS.get(symbol, []):
        df = client.get_ohlcv_history(
            measurement_name,
            report_date=report_date,
            days=days,
            timezone=timezone,
        )
        if not df.empty:
            return df
    raise ValueError(f"No OHLCV data found for {symbol}.")


def _base_asset(symbol: str) -> str:
    normalized = symbol.upper()
    return normalized[:-4] if normalized.endswith("USDT") else normalized


def _resolve_output_path(
    output_dir: Path,
    symbol: str,
    report_date: str | pd.Timestamp | None,
) -> Path:
    if report_date is None:
        return output_dir / symbol / DEFAULT_IMAGE_NAME

    target_date = pd.Timestamp(report_date).strftime("%Y-%m-%d")
    return output_dir / target_date / symbol / DEFAULT_IMAGE_NAME


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render aggregate trade volume and K-line chart from InfluxDB."
    )
    parser.add_argument(
        "symbol", nargs="?", default="ALT", help="Base asset, e.g. ALT, BB, ATA."
    )
    parser.add_argument(
        "--report-date", default=None, help="Optional report date in YYYY-MM-DD format."
    )
    parser.add_argument("--days", type=int, default=14, help="Trailing days to plot.")
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory."
    )
    parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help="Chart timezone label and aggregation timezone.",
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
        timezone=args.timezone,
    )
    print(chart.output_path)


if __name__ == "__main__":
    main()
