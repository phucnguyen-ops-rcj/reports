from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.clients.databases.influxdb import InfluxDBClient

DEFAULT_OUTPUT_DIR = Path("results/alt_bb_ata")
DEFAULT_IMAGE_NAME = "spot_order_book_imbalance.png"
SUPPORTED_SYMBOLS = {"ALT", "BB", "ATA"}
EXCHANGE_LABELS = {
    "binance": "Binance Max Level",
    "kucoin": "KuCoin Max Level",
}
EXCHANGE_COLORS = {
    "binance": "#7ecb8a",
    "kucoin": "#f4bf1a",
}


@dataclass(slots=True)
class SpotOrderBookImbalanceChart:
    symbol: str
    days: int
    output_path: Path
    data: pd.DataFrame


def build_spot_order_book_imbalance_chart(
    symbol: str,
    *,
    report_date: str | pd.Timestamp | None = None,
    days: int = 14,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    influxdb_client: InfluxDBClient | None = None,
) -> SpotOrderBookImbalanceChart:
    base_asset = _base_asset(symbol)
    client = influxdb_client or InfluxDBClient()
    chart_df = client.get_order_book_imbalance_history(base_asset, days=days)
    if chart_df.empty:
        raise ValueError(
            f"No max-level order book imbalance data found for {base_asset}/USDT."
        )

    if report_date is not None:
        end_date = pd.Timestamp(report_date).normalize()
        chart_df = chart_df[chart_df["date"] <= end_date]

    plot_df = (
        chart_df.sort_values(by=["date", "exchange"])
        .groupby("exchange", group_keys=False)
        .tail(days)
        .reset_index(drop=True)
    )
    if plot_df.empty:
        raise ValueError(
            f"No imbalance data available in the selected window for {base_asset}."
        )

    output_base = Path(output_dir)
    output_path = _resolve_output_path(output_base, base_asset, report_date)
    spot_order_book_imbalance_to_png(plot_df, output_path, base_asset=base_asset)
    return SpotOrderBookImbalanceChart(
        symbol=base_asset,
        days=days,
        output_path=output_path,
        data=plot_df,
    )


def spot_order_book_imbalance_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    base_asset: str,
    figsize: tuple[float, float] = (12, 3.7),
    dpi: int = 180,
) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    required_cols = ["date", "exchange", "value"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing imbalance columns: {', '.join(missing_cols)}")

    plot_df = df.loc[:, required_cols].dropna(subset=["date", "value"]).copy()
    plot_df["date"] = pd.to_datetime(plot_df["date"])
    plot_df = plot_df.sort_values(by=["date", "exchange"]).reset_index(drop=True)
    if plot_df.empty:
        raise ValueError("Order book imbalance data is empty.")

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    exchanges = [
        exchange
        for exchange in EXCHANGE_LABELS
        if exchange in plot_df["exchange"].unique()
    ]
    if not exchanges:
        exchanges = sorted(plot_df["exchange"].unique())

    for exchange in exchanges:
        exchange_df = plot_df[plot_df["exchange"] == exchange]
        ax.plot(
            exchange_df["date"],
            exchange_df["value"].astype(float),
            color=EXCHANGE_COLORS.get(exchange, "#4c91f7"),
            linewidth=1.2,
            marker="o",
            markersize=2.8,
            label=EXCHANGE_LABELS.get(exchange, exchange.title()),
        )

    ax.set_title(
        f"Max Level Imbalance {base_asset.upper()}",
        loc="left",
        fontsize=10,
        fontweight="bold",
        color="#2f3a45",
    )
    ax.grid(
        True, axis="both", linestyle="-", linewidth=0.6, alpha=0.18, color="#9aa0a6"
    )
    ax.tick_params(axis="x", colors="#67727d", labelsize=8, length=0)
    ax.tick_params(axis="y", colors="#67727d", labelsize=8, length=0)
    ax.set_ylabel("")
    ax.set_xlabel("")

    min_value = float(plot_df["value"].min())
    max_value = float(plot_df["value"].max())
    padding = max((max_value - min_value) * 0.14, 0.03)
    ax.set_ylim(max(0, min_value - padding), max_value + padding)

    for spine in ax.spines.values():
        spine.set_visible(False)

    xticks = plot_df["date"].drop_duplicates().sort_values()
    ax.set_xticks(xticks)
    ax.set_xticklabels([timestamp.strftime("%m/%d 00:00") for timestamp in xticks])

    legend = ax.legend(
        loc="lower left",
        frameon=False,
        fontsize=8,
        ncol=max(1, min(2, len(exchanges))),
        handlelength=1.2,
        columnspacing=0.8,
    )
    for handle in legend.legend_handles:
        handle.set_linewidth(2.0)

    plt.tight_layout(pad=0.8)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


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
        description="Render spot order book max-level imbalance chart from InfluxDB."
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        default="ALT",
        help="Base asset, e.g. ALT, BB, ATA.",
    )
    parser.add_argument(
        "--report-date",
        default=None,
        help="Optional report date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Trailing days to plot.",
    )
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

    chart = build_spot_order_book_imbalance_chart(
        symbol,
        report_date=args.report_date,
        days=args.days,
        output_dir=args.output_dir,
    )
    print(chart.output_path)


if __name__ == "__main__":
    main()
