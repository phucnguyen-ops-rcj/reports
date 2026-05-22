from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "market",
    "strategy",
    "symbol",
    "volume_$",
    "net_position",
    "net_position_$",
    "rpnl",
    "unpnl",
    "rpnlwfees",
    "npnl_r+un",
    "npnl/volume_%",
    "trade_count",
]

REPORT_COLUMN_RENAMES = {
    "Market": "market",
    "Strategy": "strategy",
    "Symbol": "symbol",
    "Volume ($)": "volume_$",
    "Net Position": "net_position",
    "Net Position$": "net_position_$",
    "RPNL": "rpnl",
    "UNPNL": "unpnl",
    "RpnlWFees": "rpnlwfees",
    "NPNL (R+UN)": "npnl_r+un",
    "NPNL/Volume (%)": "npnl/volume_%",
    "Trade Count": "trade_count",
}

STRATEGY_NORMALIZATION = {
    "strategy42": "strategy4-2",
    "strategy92": "strategy9-2",
    "kucc42": "kucc4-2",
    "kucc92": "kucc9-2",
    "strategy 4 - 2": "strategy4-2",
    "strategy 9 - 2": "strategy9-2",
    "kucc4 - 2": "kucc4-2",
    "kucc9 - 2": "kucc9-2",
}


def _normalize_strategy(value: str) -> str:
    compact = "".join(str(value).strip().lower().split())
    return STRATEGY_NORMALIZATION.get(compact, compact)


def _load_net_pnl_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns=REPORT_COLUMN_RENAMES)

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"{path} is missing required columns: {missing_cols}")

    df = df.loc[:, REQUIRED_COLUMNS].copy()
    for col in ["market", "strategy", "symbol"]:
        df[col] = df[col].fillna("").astype(str)

    df["strategy_normalized"] = df["strategy"].map(_normalize_strategy)
    df["npnl_r+un"] = pd.to_numeric(df["npnl_r+un"], errors="coerce").fillna(0.0)
    return df


def _build_outer_comparison(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["market", "strategy_normalized", "symbol"]
    merged = left_df.merge(
        right_df,
        on=keys,
        how="outer",
        suffixes=("_left", "_right"),
        indicator=True,
    )
    merged["npnl_r+un_left"] = merged["npnl_r+un_left"].fillna(0.0)
    merged["npnl_r+un_right"] = merged["npnl_r+un_right"].fillna(0.0)
    merged["npnl_diff"] = merged["npnl_r+un_left"] - merged["npnl_r+un_right"]
    merged["abs_npnl_diff"] = merged["npnl_diff"].abs()
    return merged


def _summarize_exclusive(df: pd.DataFrame, side: str) -> dict[str, float]:
    npnl_col = f"npnl_r+un_{side}"
    return {
        "rows": int(len(df)),
        "npnl_sum": float(df[npnl_col].sum()),
        "abs_npnl_sum": float(df[npnl_col].abs().sum()),
    }


def _write_outputs(
    *,
    comparison_df: pd.DataFrame,
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    comparison_df[comparison_df["_merge"] == "left_only"].sort_values(
        by="abs_npnl_diff", ascending=False
    ).to_csv(out_dir / "only_in_left.csv", index=False)
    comparison_df[comparison_df["_merge"] == "right_only"].sort_values(
        by="abs_npnl_diff", ascending=False
    ).to_csv(out_dir / "only_in_right.csv", index=False)
    comparison_df[comparison_df["_merge"] == "both"].sort_values(
        by="abs_npnl_diff", ascending=False
    ).to_csv(out_dir / "common_differences.csv", index=False)

    (
        comparison_df[comparison_df["_merge"] == "both"]
        .groupby(["market", "strategy_normalized"], as_index=False)["npnl_diff"]
        .sum()
        .assign(abs_npnl_diff=lambda df: df["npnl_diff"].abs())
        .sort_values(by="abs_npnl_diff", ascending=False)
        .to_csv(out_dir / "market_strategy_differences.csv", index=False)
    )

    (
        comparison_df[comparison_df["_merge"] == "both"]
        .groupby(["market", "symbol"], as_index=False)["npnl_diff"]
        .sum()
        .assign(abs_npnl_diff=lambda df: df["npnl_diff"].abs())
        .sort_values(by="abs_npnl_diff", ascending=False)
        .to_csv(out_dir / "market_symbol_differences.csv", index=False)
    )


def compare_net_pnl_files(
    left_path: Path,
    right_path: Path,
    *,
    output_dir: Path | None = None,
    top_n: int = 20,
) -> None:
    left_df = _load_net_pnl_csv(left_path)
    right_df = _load_net_pnl_csv(right_path)

    comparison_df = _build_outer_comparison(left_df, right_df)
    only_left = comparison_df[comparison_df["_merge"] == "left_only"].copy()
    only_right = comparison_df[comparison_df["_merge"] == "right_only"].copy()
    common_df = comparison_df[comparison_df["_merge"] == "both"].copy()

    total_left = float(left_df["npnl_r+un"].sum())
    total_right = float(right_df["npnl_r+un"].sum())
    exclusive_left = _summarize_exclusive(only_left, "left")
    exclusive_right = _summarize_exclusive(only_right, "right")
    common_diff = float(common_df["npnl_diff"].sum())

    market_strategy_diff = (
        common_df.groupby(["market", "strategy_normalized"], as_index=False)[
            "npnl_diff"
        ]
        .sum()
        .assign(abs_npnl_diff=lambda df: df["npnl_diff"].abs())
        .sort_values(by="abs_npnl_diff", ascending=False)
    )
    market_symbol_diff = (
        common_df.groupby(["market", "symbol"], as_index=False)["npnl_diff"]
        .sum()
        .assign(abs_npnl_diff=lambda df: df["npnl_diff"].abs())
        .sort_values(by="abs_npnl_diff", ascending=False)
    )

    print("Net PnL comparison")
    print(f"left file:  {left_path}")
    print(f"right file: {right_path}")
    print()
    print(
        "Total npnl_r+un:"
        f" left={total_left:.4f}"
        f" right={total_right:.4f}"
        f" diff={total_left - total_right:.4f}"
    )
    print(
        "Only in left:"
        f" rows={exclusive_left['rows']}"
        f" npnl_sum={exclusive_left['npnl_sum']:.4f}"
        f" abs_npnl_sum={exclusive_left['abs_npnl_sum']:.4f}"
    )
    print(
        "Only in right:"
        f" rows={exclusive_right['rows']}"
        f" npnl_sum={exclusive_right['npnl_sum']:.4f}"
        f" abs_npnl_sum={exclusive_right['abs_npnl_sum']:.4f}"
    )
    print("Common keys:" f" rows={len(common_df)}" f" npnl_diff_sum={common_diff:.4f}")
    print()

    print(f"Top {top_n} left-only rows by |npnl_r+un|")
    print(
        only_left.sort_values(by="abs_npnl_diff", ascending=False)[
            [
                "market",
                "strategy_left",
                "strategy_normalized",
                "symbol",
                "npnl_r+un_left",
            ]
        ]
        .head(top_n)
        .to_string(index=False)
    )
    print()

    print(f"Top {top_n} right-only rows by |npnl_r+un|")
    print(
        only_right.sort_values(by="abs_npnl_diff", ascending=False)[
            [
                "market",
                "strategy_right",
                "strategy_normalized",
                "symbol",
                "npnl_r+un_right",
            ]
        ]
        .head(top_n)
        .to_string(index=False)
    )
    print()

    print(f"Top {top_n} common rows by |npnl_r+un diff|")
    print(
        common_df.sort_values(by="abs_npnl_diff", ascending=False)[
            [
                "market",
                "strategy_normalized",
                "symbol",
                "npnl_r+un_left",
                "npnl_r+un_right",
                "npnl_diff",
            ]
        ]
        .head(top_n)
        .to_string(index=False)
    )
    print()

    print(f"Top {top_n} market+strategy buckets by |npnl_r+un diff|")
    print(market_strategy_diff.head(top_n).to_string(index=False))
    print()

    print(f"Top {top_n} market+symbol buckets by |npnl_r+un diff|")
    print(market_symbol_diff.head(top_n).to_string(index=False))

    if output_dir is not None:
        _write_outputs(comparison_df=comparison_df, out_dir=output_dir)
        print()
        print(f"Wrote detailed comparison CSVs to {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two net_pnl analysis CSV files."
    )
    parser.add_argument("left_path", type=Path)
    parser.add_argument("right_path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--top-n", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    args = parse_args()
    compare_net_pnl_files(
        args.left_path,
        args.right_path,
        output_dir=args.output_dir,
        top_n=args.top_n,
    )


if __name__ == "__main__":
    main()
    # Example:
    # uv run python -m src.scripts.compare_net_pnl \
    #   data/net_pnl/_20260522_093133.csv \
    #   data/net_pnl/analysis_data.csv \
    #   --output-dir data/net_pnl/compare_20260522
