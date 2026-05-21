from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.clients.databases.influxdb import InfluxDBClient

DEFAULT_OUTPUT_DIR = Path("results/alt_bb_ata")
DEFAULT_TIMEZONE = "UTC"
DEFAULT_SYMBOL = "ALT"
CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "volume_per_exchange.json"
)
GRID_COLOR = "#d9dde3"
BAR_COLOR = "#59b45a"
TEXT_COLOR = "#111111"
SUBTLE_TEXT_COLOR = "#6d7781"
DIVIDER_COLOR = "#7b7b7b"


@dataclass(slots=True)
class ExchangeVolumeChart:
    label: str
    measurements: list[str]
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
        str(page["filename"]),
        report_date=report_date,
    )
    volume_df = client.get_trade_notional_history(
        list(page["trade_measurements"]),
        days=days,
        report_date=report_date,
        timezone=timezone,
    )
    chart_df = _normalize_volume_history(volume_df, report_date=report_date, days=days)
    if chart_df["volume"].sum() <= 0:
        unavailable_exchange_volume_to_png(
            output_path,
            label=str(page["label"]),
            page_no=int(page["page_no"]),
            page_count=int(page["page_count"]),
            days=days,
            report_date=report_date,
            timezone=timezone,
            measurements=list(page["trade_measurements"]),
        )
        return ExchangeVolumeChart(
            label=str(page["label"]),
            measurements=list(page["trade_measurements"]),
            output_path=output_path,
            data=chart_df,
            available=False,
        )

    exchange_volume_to_png(
        chart_df,
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
        measurements=list(page["trade_measurements"]),
        output_path=output_path,
        data=chart_df,
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
        f"Volume per exchange [{page_no} of {page_count}] {days} days window     {plot_start} - {plot_end} / {timezone} 00:00-00:00",
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
        f"{label} Trade volume - 24 hr interval",
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
    ax.set_ylim(0, max_volume * 1.14 if max_volume > 0 else 1.0)

    for bar, value in zip(bars, plot_df["volume"], strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(max_volume * 0.015, 1.0),
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
    measurements: list[str],
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
        f"Volume per exchange [{page_no} of {page_count}] {days} days window     {start_date} - {end_date} / {timezone} 00:00-00:00",
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
        f"{label} Trade volume - 24 hr interval",
        ha="left",
        va="top",
        fontsize=17,
        color=TEXT_COLOR,
    )
    fig.text(
        0.5,
        0.44,
        "No trade volume data available",
        ha="center",
        va="center",
        fontsize=18,
        color=TEXT_COLOR,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.32,
        ", ".join(measurements),
        ha="center",
        va="center",
        fontsize=10,
        color=SUBTLE_TEXT_COLOR,
    )

    fig.subplots_adjust(left=0.03, right=0.98, bottom=0.08, top=0.76)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def build_all_exchange_volume_charts(
    *,
    symbol: str = DEFAULT_SYMBOL,
    report_date: str | pd.Timestamp | None = None,
    days: int = 14,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    timezone: str = DEFAULT_TIMEZONE,
    influxdb_client: InfluxDBClient | None = None,
) -> list[ExchangeVolumeChart]:
    client = influxdb_client or InfluxDBClient()
    charts: list[ExchangeVolumeChart] = []
    for page in _load_symbol_pages(symbol):
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


def _load_symbol_pages(symbol: str) -> list[dict[str, object]]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    pages = payload.get(symbol.upper())
    if not isinstance(pages, list) or not pages:
        raise ValueError(f"No volume-per-exchange configuration found for {symbol}.")
    return pages


def _normalize_volume_history(
    volume_df: pd.DataFrame,
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> pd.DataFrame:
    start_date, end_date = _window_date_timestamps(report_date=report_date, days=days)
    date_index = pd.date_range(start_date, end_date, freq="D")
    if volume_df.empty:
        return pd.DataFrame({"date": date_index, "volume": [0.0] * len(date_index)})
    daily_df = (
        volume_df.groupby("date", as_index=False)
        .agg(volume=("our_notional", "sum"))
        .set_index("date")
        .reindex(date_index, fill_value=0.0)
        .rename_axis("date")
        .reset_index()
    )
    return daily_df.loc[:, ["date", "volume"]]


def _resolve_output_path(
    output_dir: Path,
    filename: str,
    *,
    report_date: str | pd.Timestamp | None,
) -> Path:
    if report_date is None:
        return output_dir / DEFAULT_SYMBOL / filename
    target_date = pd.Timestamp(report_date).strftime("%Y-%m-%d")
    return output_dir / target_date / DEFAULT_SYMBOL / filename


def _window_dates(
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> tuple[str, str]:
    start_date, end_date = _window_date_timestamps(report_date=report_date, days=days)
    return start_date.strftime("%-d %B"), end_date.strftime("%-d %B")


def _window_date_timestamps(
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if report_date is None:
        end_date = pd.Timestamp.now(tz="UTC").normalize()
    else:
        end_date = pd.Timestamp(report_date)
        if end_date.tzinfo is None:
            end_date = end_date.tz_localize("UTC")
        else:
            end_date = end_date.tz_convert("UTC")
        end_date = end_date.normalize()
    start_date = end_date - pd.Timedelta(days=days - 1)
    return start_date.tz_localize(None), end_date.tz_localize(None)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render per-exchange ALT volume charts from trade-fill Influx measurements."
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
