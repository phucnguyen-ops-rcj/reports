from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from src.clients.databases.influxdb import InfluxDBClient
from src.scripts.alt_bb_ata.liquidity_public_data import (
    build_public_clients,
    calculate_period_market_share,
    load_liquidity_row_configs,
    load_public_liquidity_metrics,
)

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("results/alt_bb_ata")
DEFAULT_IMAGE_NAME = "liquidity_summary_table.png"
DEFAULT_BUCKET = "Prod"
DEFAULT_TIMEZONE = "UTC"


@dataclass(slots=True)
class LiquidityTableChart:
    symbol: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    output_path: Path
    data: pd.DataFrame


def build_liquidity_table_chart(
    symbol: str,
    *,
    report_date: str | pd.Timestamp | None = None,
    days: int = 14,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    influxdb_client: InfluxDBClient | None = None,
    public_clients: dict[str, Any] | None = None,
) -> LiquidityTableChart:
    chart_df = load_liquidity_table_data(
        symbol,
        report_date=report_date,
        days=days,
        influxdb_client=influxdb_client,
        public_clients=public_clients,
    )
    start_date, end_date = _window_dates(report_date=report_date, days=days)
    output_path = _resolve_output_path(
        Path(output_dir),
        symbol.upper(),
        report_date=report_date,
    )
    liquidity_table_to_png(
        chart_df,
        output_path,
        symbol=symbol.upper(),
        start_date=start_date,
        end_date=end_date,
        days=days,
    )
    return LiquidityTableChart(
        symbol=symbol.upper(),
        start_date=start_date,
        end_date=end_date,
        output_path=output_path,
        data=chart_df,
    )


def load_liquidity_table_data(
    symbol: str,
    *,
    report_date: str | pd.Timestamp | None = None,
    days: int = 14,
    influxdb_client: InfluxDBClient | None = None,
    public_clients: dict[str, Any] | None = None,
    row_configs: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    base_asset = symbol.upper()
    rows_config = row_configs or load_liquidity_row_configs(base_asset)
    client = influxdb_client or InfluxDBClient()
    exchange_clients = public_clients or build_public_clients()
    records: list[dict[str, Any]] = []

    for row in rows_config:
        exchange = str(row["exchange"])
        exchange_client = exchange_clients[exchange]
        public_symbol = str(row["public_symbol"])
        trade_history = client.get_trade_notional_history(
            list(row["trade_measurements"]),
            bucket=DEFAULT_BUCKET,
            days=days,
            report_date=report_date,
            timezone=DEFAULT_TIMEZONE,
        )
        try:
            market_plus_depth, market_minus_depth, public_volume_history = (
                load_public_liquidity_metrics(
                    exchange_client,
                    public_symbol,
                    report_date=report_date,
                    days=days,
                )
            )
        except Exception:
            market_plus_depth = None
            market_minus_depth = None
            public_volume_history = pd.DataFrame(columns=["date", "quote_volume"])
            logger.warning(
                "Failed to load public liquidity metrics for %s %s.",
                exchange,
                public_symbol,
                exc_info=True,
            )

        market_share = calculate_period_market_share(
            trade_history,
            public_volume_history,
        )
        records.append(
            {
                "exchange": row["exchange_label"],
                "pair": row["pair"],
                "market_plus_depth": market_plus_depth,
                "market_minus_depth": market_minus_depth,
                "our_spread_bps": float(row["spread_bps"]),
                "weekly_average_market_share": market_share,
            }
        )

    return pd.DataFrame(
        records,
        columns=[
            "exchange",
            "pair",
            "market_plus_depth",
            "market_minus_depth",
            "our_spread_bps",
            "weekly_average_market_share",
        ],
    )


def liquidity_table_to_png(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    days: int,
    figsize: tuple[float, float] = (13.5, 4.6),
    dpi: int = 180,
) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    display_df = pd.DataFrame(
        {
            "Exchange": df["exchange"],
            "Pair": df["pair"],
            "Market +2% Depth": df["market_plus_depth"].apply(_format_usd),
            "Market -2% Depth": df["market_minus_depth"].apply(_format_usd),
            "Our Spread": df["our_spread_bps"].apply(_format_bps),
            "Weekly Average Market Share": df["weekly_average_market_share"].apply(
                _format_share
            ),
        }
    )

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.axis("off")

    fig.text(
        0.03,
        0.96,
        f"{symbol} Liquidity Summary",
        ha="left",
        va="top",
        fontsize=12,
        fontweight="bold",
        color="#111111",
    )
    fig.text(
        0.03,
        0.90,
        f"{symbol} : Window of {start_date.strftime('%-d %B')} - {end_date.strftime('%-d %B')} UTC 00:00-23:59",
        ha="left",
        va="top",
        fontsize=10.5,
        color="#222222",
    )
    fig.text(
        0.03,
        0.84,
        f"Depth uses current public order-book snapshots. Market share uses total private notional divided by total public quote volume over the trailing {days}-day window.",
        ha="left",
        va="top",
        fontsize=8.5,
        color="#5f6770",
    )

    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        cellLoc="center",
        loc="center",
        bbox=[0.03, 0.05, 0.94, 0.70],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)

    for col in range(len(display_df.columns)):
        header_cell = table[(0, col)]
        header_cell.set_facecolor("#dce7f5")
        header_cell.set_text_props(weight="bold", color="#1b2430")
        header_cell.set_edgecolor("#6b7280")
        header_cell.set_linewidth(0.8)

    for row_index in range(1, len(display_df) + 1):
        for col_index in range(len(display_df.columns)):
            body_cell = table[(row_index, col_index)]
            body_cell.set_facecolor("white")
            body_cell.set_edgecolor("#6b7280")
            body_cell.set_linewidth(0.8)
            if col_index == 0:
                body_cell.set_text_props(weight="bold", color="#111111")

    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def _resolve_output_path(
    output_dir: Path,
    symbol: str,
    report_date: str | pd.Timestamp | None,
) -> Path:
    _ = symbol
    _ = report_date
    return output_dir / DEFAULT_IMAGE_NAME


def _window_dates(
    *,
    report_date: str | pd.Timestamp | None,
    days: int,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if report_date is None:
        end_date = pd.Timestamp.now(tz=DEFAULT_TIMEZONE).normalize()
    else:
        end_date = pd.Timestamp(report_date)
        if end_date.tzinfo is None:
            end_date = end_date.tz_localize(DEFAULT_TIMEZONE)
        else:
            end_date = end_date.tz_convert(DEFAULT_TIMEZONE)
        end_date = end_date.normalize()
    start_date = end_date - pd.Timedelta(days=days - 1)
    return start_date.tz_localize(None), end_date.tz_localize(None)


def _format_usd(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"${int(round(value)):,.0f}"


def _format_bps(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"~{int(round(value))}bps"


def _format_share(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"~{value * 100:.0f}%"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render simplified liquidity summary table for ALT report."
    )
    parser.add_argument("symbol", nargs="?", default="ALT", help="Base asset.")
    parser.add_argument("--report-date", default=None, help="Optional YYYY-MM-DD.")
    parser.add_argument("--days", type=int, default=14, help="Trailing window.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory.",
    )
    args = parser.parse_args()

    chart = build_liquidity_table_chart(
        args.symbol,
        report_date=args.report_date,
        days=args.days,
        output_dir=args.output_dir,
    )
    print(chart.output_path)


if __name__ == "__main__":
    main()
