from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.clients.databases.influxdb import InfluxDBClient

DEFAULT_OUTPUT_DIR = Path("results/alt_bb_ata")
DEFAULT_TIMEZONE = "UTC"
GRID_COLOR = "#d9dde3"
BAR_COLOR = "#59b45a"
TEXT_COLOR = "#111111"
SUBTLE_TEXT_COLOR = "#6d7781"
DIVIDER_COLOR = "#7b7b7b"

EXCHANGE_VOLUME_PAGES = [
    {
        "page_no": 2,
        "page_count": 6,
        "label": "Binance ALTUSDT",
        "measurement": "binance_ALTUSDT_ohlcv",
        "filename": "binance_altusdt_volume.png",
    },
    {
        "page_no": 3,
        "page_count": 6,
        "label": "Binance ALTUSDC",
        "measurement": "binance_ALTUSDC_ohlcv",
        "filename": "binance_altusdc_volume.png",
    },
    {
        "page_no": 4,
        "page_count": 6,
        "label": "KuCoin ALTUSDT",
        "measurement": "kucoin_KALT-USDT_ohlcv",
        "filename": "kucoin_altusdt_volume.png",
    },
    {
        "page_no": 5,
        "page_count": 6,
        "label": "Gate ALTUSDT",
        "measurement": "gateio_ALT_USDT_ohlcv",
        "filename": "gate_altusdt_volume.png",
    },
    {
        "page_no": 6,
        "page_count": 6,
        "label": "Bybit ALTUSDT",
        "measurement": "bybit_ALTUSDT_ohlcv",
        "filename": "bybit_altusdt_volume.png",
    },
]


@dataclass(slots=True)
class ExchangeVolumeChart:
    label: str
    measurement: str
    output_path: Path
    data: pd.DataFrame
    available: bool


def build_exchange_volume_chart(
    page: dict[str, object],
    *,
    report_date: str | pd.Timestamp | None = None,
    days: int = 14,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    timezone: str = DEFAULT_TIMEZONE,
    influxdb_client: InfluxDBClient | None = None,
) -> ExchangeVolumeChart:
    client = influxdb_client or InfluxDBClient()
    output_path = _resolve_output_path(
        Path(output_dir),
        page["filename"],
        report_date=report_date,
    )
    volume_df = client.get_ohlcv_volume_history(
        str(page["measurement"]),
        report_date=report_date,
        days=days,
        timezone=timezone,
    )
    if volume_df.empty:
        unavailable_exchange_volume_to_png(
            output_path,
            label=str(page["label"]),
            page_no=int(page["page_no"]),
            page_count=int(page["page_count"]),
            days=days,
            report_date=report_date,
            timezone=timezone,
            measurement=str(page["measurement"]),
        )
        return ExchangeVolumeChart(
            label=str(page["label"]),
            measurement=str(page["measurement"]),
            output_path=output_path,
            data=volume_df,
            available=False,
        )

    exchange_volume_to_png(
        volume_df,
        output_path,
        label=str(page["label"]),
        page_no=int(page["page_no"]),
        page_count=int(page["page_count"]),
        days=days,
        report_date=report_date,
        timezone=timezone,
    )
    return ExchangeVolumeChart(
        label=str(page["label"]),
        measurement=str(page["measurement"]),
        output_path=output_path,
        data=volume_df,
        available=True,
    )


def exchange_volume_to_png(
    volume_df: pd.DataFrame,
    output_path: str | Path,
    *,
    label: str,
    page_no: int,
    page_count: int,
    days: int,
    report_date: str | pd.Timestamp | None,
    timezone: str,
    figsize: tuple[float, float] = (13.5, 4.8),
    dpi: int = 220,
) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    plot_df = volume_df.sort_values(by="date").tail(days).reset_index(drop=True)
    if plot_df.empty:
        raise ValueError("Volume data is empty.")

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    dates = plot_df["date"]
    x = np.arange(len(plot_df))
    bars = ax.bar(
        x,
        plot_df["volume"].astype(float),
        width=0.94,
        color=BAR_COLOR,
        edgecolor=BAR_COLOR,
        alpha=0.92,
        zorder=3,
    )

    plot_start = dates.min().strftime("%-d %B")
    plot_end = dates.max().strftime("%-d %B")
    fig.text(
        0.045,
        0.92,
        f"Volume per exchange  [{page_no} of {page_count}] {days} days window     {plot_start} - {plot_end}  / {timezone} 00:00-00:00",
        ha="left",
        va="top",
        fontsize=14,
        color=TEXT_COLOR,
    )
    fig.add_artist(
        plt.Line2D(
            [0.045, 0.86],
            [0.855, 0.855],
            transform=fig.transFigure,
            color=DIVIDER_COLOR,
            linewidth=0.8,
        )
    )
    fig.text(
        0.045,
        0.81,
        f"{label} Trade volume– 24 hr interval",
        ha="left",
        va="top",
        fontsize=17,
        color=TEXT_COLOR,
    )

    ax.grid(True, axis="y", linestyle="-", linewidth=0.6, alpha=0.25, color=GRID_COLOR)
    ax.grid(False, axis="x")
    ax.tick_params(axis="x", colors=SUBTLE_TEXT_COLOR, labelsize=10, length=0)
    ax.tick_params(axis="y", colors=SUBTLE_TEXT_COLOR, labelsize=9, length=0)
    ax.set_xticks(x)
    ax.set_xticklabels([d.strftime("%m/%d 00:00") for d in dates])
    ax.set_yticklabels([])

    max_volume = float(plot_df["volume"].max())
    ax.set_ylim(0, max_volume * 1.14)

    for bar, value in zip(bars, plot_df["volume"], strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_volume * 0.015,
            f"{int(round(float(value)))}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#7c858f",
            fontweight="bold",
        )

    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.subplots_adjust(left=0.06, right=0.98, bottom=0.2, top=0.72)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def unavailable_exchange_volume_to_png(
    output_path: str | Path,
    *,
    label: str,
    page_no: int,
    page_count: int,
    days: int,
    report_date: str | pd.Timestamp | None,
    timezone: str,
    measurement: str,
    figsize: tuple[float, float] = (13.5, 4.8),
    dpi: int = 220,
) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.axis("off")

    start_date, end_date = _window_dates(report_date=report_date, days=days)
    fig.text(
        0.045,
        0.92,
        f"Volume per exchange  [{page_no} of {page_count}] {days} days window     {start_date} - {end_date}  / {timezone} 00:00-00:00",
        ha="left",
        va="top",
        fontsize=14,
        color=TEXT_COLOR,
    )
    fig.add_artist(
        plt.Line2D(
            [0.045, 0.86],
            [0.855, 0.855],
            transform=fig.transFigure,
            color=DIVIDER_COLOR,
            linewidth=0.8,
        )
    )
    fig.text(
        0.045,
        0.81,
        f"{label} Trade volume– 24 hr interval",
        ha="left",
        va="top",
        fontsize=17,
        color=TEXT_COLOR,
    )
    fig.text(
        0.5,
        0.44,
        "No OHLCV volume data available",
        ha="center",
        va="center",
        fontsize=18,
        color=TEXT_COLOR,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.34,
        measurement,
        ha="center",
        va="center",
        fontsize=12,
        color=SUBTLE_TEXT_COLOR,
    )

    fig.subplots_adjust(left=0.03, right=0.98, bottom=0.08, top=0.76)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def build_all_exchange_volume_charts(
    *,
    report_date: str | pd.Timestamp | None = None,
    days: int = 14,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    timezone: str = DEFAULT_TIMEZONE,
    influxdb_client: InfluxDBClient | None = None,
) -> list[ExchangeVolumeChart]:
    client = influxdb_client or InfluxDBClient()
    charts: list[ExchangeVolumeChart] = []
    for page in EXCHANGE_VOLUME_PAGES:
        charts.append(
            build_exchange_volume_chart(
                page,
                report_date=report_date,
                days=days,
                output_dir=output_dir,
                timezone=timezone,
                influxdb_client=client,
            )
        )
    return charts


def _resolve_output_path(
    output_dir: Path,
    filename: str,
    *,
    report_date: str | pd.Timestamp | None,
) -> Path:
    if report_date is None:
        return output_dir / "ALT" / filename
    target_date = pd.Timestamp(report_date).strftime("%Y-%m-%d")
    return output_dir / target_date / "ALT" / filename


def _window_dates(
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> tuple[str, str]:
    if report_date is None:
        end_date = pd.Timestamp.utcnow().normalize().tz_localize("UTC")
    else:
        end_date = pd.Timestamp(report_date)
        if end_date.tzinfo is None:
            end_date = end_date.tz_localize("UTC")
        else:
            end_date = end_date.tz_convert("UTC")
        end_date = end_date.normalize()
    start_date = end_date - pd.Timedelta(days=days - 1)
    return start_date.strftime("%-d %B"), end_date.strftime("%-d %B")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render per-exchange ALT volume charts from OHLCV Influx measurements."
    )
    parser.add_argument(
        "--report-date", default=None, help="Report date in YYYY-MM-DD format."
    )
    parser.add_argument("--days", type=int, default=14, help="Trailing days to plot.")
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory."
    )
    parser.add_argument(
        "--timezone", default=DEFAULT_TIMEZONE, help="Aggregation timezone."
    )
    args = parser.parse_args()

    charts = build_all_exchange_volume_charts(
        report_date=args.report_date,
        days=args.days,
        output_dir=args.output_dir,
        timezone=args.timezone,
    )
    for chart in charts:
        print(chart.output_path)


if __name__ == "__main__":
    main()
