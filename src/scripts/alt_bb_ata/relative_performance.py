from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

from src.clients.exchanges.binance import BinanceClient
from src.clients.third_parties.coingecko import CoinGeckoClient

DEFAULT_COINGECKO_COIN_IDS = {
    "ALT": "altlayer",
    "BB": "bouncebit",
    "ATA": "automata",
}


@dataclass(slots=True)
class RelativePerformanceData:
    symbol: str
    candles: pd.DataFrame
    market_cap_series: pd.DataFrame
    market_cap_source: str


def build_relative_performance_sentence(
    symbol: str, *, days: int = 7
) -> tuple[str, str]:
    base_asset = symbol.upper()
    return (
        f"Overall, {base_asset} traded in line with the rest of the crypto market over the past week.",
        f"The chart below shows {base_asset} (K-line) relative to overall crypto market cap excluding BTC and ETH (orange).",
    )


def load_relative_performance_data(
    symbol: str,
    *,
    days: int = 14,
    market_cap_top_n: int = 30,
    binance_client: BinanceClient | None = None,
    coingecko_client: CoinGeckoClient | None = None,
) -> RelativePerformanceData:
    base_asset = symbol.upper()
    binance = binance_client or BinanceClient()
    coingecko = coingecko_client or CoinGeckoClient()

    candles = _load_binance_daily_candles(binance, base_asset, days=days)
    market_cap_series, market_cap_source = _load_market_cap_ex_btc_eth_series(
        coingecko,
        days=days,
        market_cap_top_n=market_cap_top_n,
    )
    return RelativePerformanceData(
        symbol=base_asset,
        candles=candles,
        market_cap_series=market_cap_series,
        market_cap_source=market_cap_source,
    )


def relative_performance_to_png(
    symbol: str,
    output_path: str | Path | None = None,
    *,
    days: int = 14,
    market_cap_top_n: int = 500,
    figsize: tuple[float, float] = (11, 5.2),
    dpi: int = 220,
) -> Path:
    data = load_relative_performance_data(
        symbol,
        days=days,
        market_cap_top_n=market_cap_top_n,
    )

    out_path = (
        Path(output_path) if output_path is not None else _default_output_path(symbol)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    candles = data.candles.copy()
    market_cap = data.market_cap_series.copy()
    if candles.empty:
        raise ValueError(f"No Binance candle data found for {data.symbol}.")
    if market_cap.empty:
        raise ValueError("No market cap data found.")

    candle_dates = mdates.date2num(
        candles["date"].dt.to_pydatetime()
    )  # pyrefly: ignore
    market_dates = mdates.date2num(
        market_cap["date"].dt.to_pydatetime()
    )  # pyrefly: ignore
    candle_width = 0.62

    fig, ax_market = plt.subplots(figsize=figsize)
    ax_price = ax_market.twinx()

    fig.patch.set_facecolor("white")
    ax_market.set_facecolor("white")
    ax_market.grid(True, axis="both", linestyle="-", linewidth=0.6, alpha=0.18)

    ax_market.plot(
        market_dates,
        market_cap["market_cap_billions"],
        color="#ff8c33",
        linewidth=1.5,
        zorder=2,
    )

    for x, row in zip(candle_dates, candles.itertuples(index=False), strict=False):
        open_price = float(row.open_price)
        high_price = float(row.high_price)
        low_price = float(row.low_price)
        close_price = float(row.close_price)
        color = "#16a085" if close_price >= open_price else "#f03e3e"
        ax_price.vlines(x, low_price, high_price, color=color, linewidth=1.0, zorder=3)
        body_low = min(open_price, close_price)
        body_height = max(abs(close_price - open_price), 1e-12)
        ax_price.add_patch(
            Rectangle(
                (x - candle_width / 2, body_low),
                candle_width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.7,
                zorder=4,
            )
        )

    ax_market.set_ylabel("Market cap ex BTC/ETH (USD bn)", color="#666666", fontsize=10)
    ax_price.set_ylabel(f"{data.symbol} price (USD)", color="#666666", fontsize=10)
    ax_market.tick_params(axis="y", colors="#666666", labelsize=9, length=0)
    ax_price.tick_params(axis="y", colors="#666666", labelsize=9, length=0)
    ax_market.tick_params(axis="x", colors="#666666", labelsize=9, length=0)

    locator = mdates.AutoDateLocator(minticks=5, maxticks=9)
    ax_market.xaxis.set_major_locator(locator)
    ax_market.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    for spine in (*ax_market.spines.values(), *ax_price.spines.values()):
        spine.set_visible(False)

    ax_market.set_xlim(
        min(candle_dates.min(), market_dates.min()) - 0.5,
        max(candle_dates.max(), market_dates.max()) + 0.7,
    )

    latest_market = market_cap.iloc[-1]
    latest_candle = candles.iloc[-1]
    ax_market.annotate(
        f"TOTAL3\n{latest_market['market_cap_billions']:.1f} B",
        xy=(market_dates[-1], latest_market["market_cap_billions"]),
        xytext=(10, 0),
        textcoords="offset points",
        ha="left",
        va="center",
        color="white",
        fontsize=9,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#ff8c33", edgecolor="#ff8c33"),
        zorder=6,
    )
    ax_price.annotate(
        f"{data.symbol}\n{_format_price(float(latest_candle.close_price))}",
        xy=(candle_dates[-1], float(latest_candle.close_price)),
        xytext=(10, 0),
        textcoords="offset points",
        ha="left",
        va="center",
        color="white",
        fontsize=9,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#16a085", edgecolor="#16a085"),
        zorder=6,
    )

    plt.tight_layout()
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def _load_binance_daily_candles(
    client: BinanceClient,
    symbol: str,
    *,
    days: int,
) -> pd.DataFrame:
    resolved_symbol = _to_usdt_symbol(symbol)
    try:
        klines = client.get_klines(resolved_symbol, interval="1d", limit=days + 2)
    except Exception:
        try:
            klines = client.get_futures_klines(
                resolved_symbol,
                interval="1d",
                limit=days + 2,
            )
        except Exception:
            klines = []
    if not klines:
        return _load_coin_gecko_price_candles(symbol, days=days)

    df = pd.DataFrame([kline.model_dump() for kline in klines])
    df["date"] = pd.to_datetime(df["open_time_ms"], unit="ms", utc=True)
    df = df.sort_values(by="date").tail(days).reset_index(drop=True)
    return df.loc[:, ["date", "open_price", "high_price", "low_price", "close_price"]]


def _load_coin_gecko_price_candles(symbol: str, *, days: int) -> pd.DataFrame:
    client = CoinGeckoClient()
    coin_id = DEFAULT_COINGECKO_COIN_IDS.get(symbol.upper())
    if coin_id is None:
        coin_id = client.resolve_coin_id(symbol, preferred_ids=[symbol.lower()])
    if not coin_id:
        return pd.DataFrame(
            columns=["date", "open_price", "high_price", "low_price", "close_price"]
        )

    try:
        prices = client.get_coin_price_chart(coin_id, days=days)
    except Exception:
        return pd.DataFrame(
            columns=["date", "open_price", "high_price", "low_price", "close_price"]
        )

    if prices.empty:
        return pd.DataFrame(
            columns=["date", "open_price", "high_price", "low_price", "close_price"]
        )

    df = prices.copy()
    df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True).dt.floor(
        "D"
    )  # pyrefly: ignore
    df = df.dropna(subset=["price"])
    df = (
        df.sort_values(by="timestamp_ms")
        .groupby("date", as_index=False)
        .agg(
            open_price=("price", "first"),
            high_price=("price", "max"),
            low_price=("price", "min"),
            close_price=("price", "last"),
        )
    )
    return df.loc[:, ["date", "open_price", "high_price", "low_price", "close_price"]]


def _load_market_cap_ex_btc_eth_series(
    client: CoinGeckoClient,
    *,
    days: int,
    market_cap_top_n: int,
) -> tuple[pd.DataFrame, str]:
    exact_series = _try_exact_market_cap_series(client, days=days)
    if exact_series is not None and not exact_series.empty:
        return exact_series, "exact"

    return _approximate_market_cap_series(
        client,
        days=days,
        market_cap_top_n=market_cap_top_n,
    )


def _try_exact_market_cap_series(
    client: CoinGeckoClient, *, days: int
) -> pd.DataFrame | None:
    try:
        global_df = client.get_global_market_cap_chart(days=days)
        btc_df = client.get_coin_market_chart("bitcoin", days=days)
        eth_df = client.get_coin_market_chart("ethereum", days=days)
    except Exception:
        return None

    merged = (
        _daily_market_cap_frame(global_df, prefix="global")
        .merge(_daily_market_cap_frame(btc_df, prefix="btc"), on="date", how="outer")
        .merge(_daily_market_cap_frame(eth_df, prefix="eth"), on="date", how="outer")
        .sort_values(by="date")
        .reset_index(drop=True)
    )
    merged["market_cap"] = (
        merged["global_market_cap"]
        .fillna(0.0)
        .sub(merged["btc_market_cap"].fillna(0.0))
        .sub(merged["eth_market_cap"].fillna(0.0))
    )
    merged = merged.loc[merged["market_cap"] > 0, ["date", "market_cap"]].copy()
    if merged.empty:
        return None
    merged["market_cap_billions"] = merged["market_cap"] / 1_000_000_000
    return merged


def _approximate_market_cap_series(
    client: CoinGeckoClient,
    *,
    days: int,
    market_cap_top_n: int,
) -> tuple[pd.DataFrame, str]:
    markets = client.get_coin_markets(per_page=max(market_cap_top_n + 2, 20), page=1)
    candidate_ids = [
        market.id for market in markets if market.id not in {"bitcoin", "ethereum"}
    ][:market_cap_top_n]

    if not candidate_ids:
        return pd.DataFrame(
            columns=["date", "market_cap", "market_cap_billions"]
        ), "approx"

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=min(8, len(candidate_ids))) as executor:
        future_map = {
            executor.submit(_fetch_market_cap_series, client, coin_id, days): coin_id
            for coin_id in candidate_ids
        }
        for future in as_completed(future_map):
            frame = future.result()
            if frame is not None and not frame.empty:
                frames.append(frame)

    if not frames:
        return pd.DataFrame(
            columns=["date", "market_cap", "market_cap_billions"]
        ), "approx"

    combined = frames[0].copy()
    for frame in frames[1:]:
        combined = combined.merge(frame, on="date", how="outer")

    numeric_cols = [col for col in combined.columns if col != "date"]
    combined["market_cap"] = combined.loc[:, numeric_cols].fillna(0.0).sum(axis=1)
    combined = combined.loc[:, ["date", "market_cap"]].copy()

    combined = combined.sort_values(by="date").reset_index(drop=True)
    combined["market_cap_billions"] = combined["market_cap"] / 1_000_000_000
    return combined, "approx"


def _fetch_market_cap_series(
    client: CoinGeckoClient,
    coin_id: str,
    days: int,
) -> pd.DataFrame | None:
    try:
        frame = client.get_coin_market_chart(coin_id, days=days)
    except Exception:
        return None
    if frame.empty:
        return None
    return _daily_market_cap_frame(frame, prefix=coin_id)


def _daily_market_cap_frame(frame: pd.DataFrame, *, prefix: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["date", f"{prefix}_market_cap"])

    df = frame.copy()
    df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True).dt.floor(
        "D"
    )  # pyrefly: ignore
    df = (
        df.sort_values(by="timestamp_ms")
        .groupby("date", as_index=False)
        .tail(1)
        .loc[:, ["date", "market_cap"]]
        .rename(columns={"market_cap": f"{prefix}_market_cap"})
    )
    return df


def _format_price(value: float) -> str:
    return f"{value:.4f}" if abs(value) < 1 else f"{value:.2f}"


def _to_usdt_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    return normalized if normalized.endswith("USDT") else f"{normalized}USDT"


def _default_output_path(symbol: str) -> Path:
    base_asset = symbol.upper()
    if base_asset.endswith("USDT"):
        base_asset = base_asset[:-4]
    return Path("results") / "market" / f"{base_asset.lower()}_relative_performance.png"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Render a relative performance chart.")
    parser.add_argument(
        "symbol", nargs="?", default="BB", help="Base asset, e.g. BB or ALT."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output PNG path. Defaults to results/market/{symbol}_relative_performance.png.",
    )
    parser.add_argument("--days", type=int, default=14, help="Number of trailing days.")
    parser.add_argument(
        "--market-cap-top-n",
        type=int,
        default=1000,
        help="Approximation breadth when the exact global market cap series is unavailable.",
    )
    args = parser.parse_args()

    output = relative_performance_to_png(
        args.symbol,
        args.output,
        days=args.days,
        market_cap_top_n=args.market_cap_top_n,
    )
    print(output)


if __name__ == "__main__":
    main()
