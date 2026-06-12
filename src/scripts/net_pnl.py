from pathlib import Path
import logging
import pandas as pd
from src.settings import app_settings
from src.clients.signal import SignalClient
from src.utils.load_data import load_pnl_data
from src.utils.constants import (
    THRESHOLDS,
    FINAL_COLUMNS,
    STRATEGY_NAME_MAPPING,
    STRATEGY_CATEGORY_MAPPING,
)
from src.utils.dataframe import (
    aggregate_metric_columns,
    calculate_ratio_column,
    filter_rows_below_threshold,
    map_column_with_fallback,
)
from src.utils.format_message import build_daily_report
from src.utils.save_data import save_report, save_csv
from src.utils.visualization import net_pnl_to_png_styled

logger = logging.getLogger(__name__)

LARGE_PROFIT_THRESHOLD = 20_000


def build_group_summary(df, by_cols):
    summary_df = aggregate_metric_columns(df, by_cols, FINAL_COLUMNS[1:])
    return calculate_ratio_column(
        summary_df, "npnl_r+un", "volume_$", "npnl/volume_%", scale=100
    )


def add_strategy_name(df, key_col):
    return map_column_with_fallback(df, key_col, "name", STRATEGY_NAME_MAPPING)


def add_strategy_category(df, key_col):
    return map_column_with_fallback(df, key_col, "category", STRATEGY_CATEGORY_MAPPING)


def _analyze_base_strategy_losses(df):
    """Identify base strategies with losses."""
    base_strat_sum = build_group_summary(df, ["base_strategy"])
    loss_base_strats_df = filter_rows_below_threshold(
        base_strat_sum,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )
    return loss_base_strats_df["base_strategy"].tolist()


def _build_strategy_summary_table(df):
    """Build strategy summary with categories and total row."""
    strat_sum = build_group_summary(df, ["strategy"])
    w_category_strat_sum_df = add_strategy_category(strat_sum, "strategy")
    w_category_strat_sum_df["category_total_npnl"] = w_category_strat_sum_df.groupby(
        "category"
    )["npnl_r+un"].transform("sum")
    w_category_strat_sum_df = calculate_ratio_column(
        w_category_strat_sum_df, "npnl_r+un", "volume_$", "npnl/volume_%", scale=100
    )
    w_category_strat_sum_df.sort_values(
        ["category_total_npnl", "strategy"], inplace=True, ascending=[True, True]
    )
    category_total_npnl_sum = w_category_strat_sum_df.drop_duplicates(
        subset=["category"]
    )["category_total_npnl"].sum()

    _total_row = pd.DataFrame(
        {
            "strategy": ["Total"],
            "volume_$": [w_category_strat_sum_df["volume_$"].sum()],
            "npnl_r+un": [w_category_strat_sum_df["npnl_r+un"].sum()],
            "npnl/volume_%": [
                round(
                    w_category_strat_sum_df["npnl_r+un"].sum()
                    / strat_sum["volume_$"].sum()
                    * 100,
                    2,
                )
            ],
            "net_position_$": [w_category_strat_sum_df["net_position_$"].sum()],
            "unpnl": [w_category_strat_sum_df["unpnl"].sum()],
            "rpnlwfees": [w_category_strat_sum_df["rpnlwfees"].sum()],
            "category": ["-"],
            "category_total_npnl": [category_total_npnl_sum],
        }
    )
    return pd.concat([w_category_strat_sum_df, _total_row], ignore_index=True)


def _analyze_symbol_losses(df):
    """Identify symbols with losses and severe losses."""
    sym_sum = build_group_summary(df, ["mapped_symbol"])
    loss_sym_df = filter_rows_below_threshold(
        sym_sum,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )
    loss_symbols = loss_sym_df["mapped_symbol"].tolist()
    severe_sym_df = filter_rows_below_threshold(sym_sum, "npnl_r+un", -3000)
    severe_symbols = severe_sym_df["mapped_symbol"].tolist()
    return loss_sym_df, loss_symbols, severe_symbols


def _analyze_large_profit_symbols(df):
    """Identify symbols with NPNL above the large-profit threshold."""
    sym_sum = build_group_summary(df, ["mapped_symbol"])
    large_profit_sym_df = sym_sum[sym_sum["npnl_r+un"] > LARGE_PROFIT_THRESHOLD].copy()
    large_profit_sym_df.sort_values(by="npnl_r+un", inplace=True, ascending=False)
    return large_profit_sym_df["mapped_symbol"].tolist()


def _build_symbol_strategy_detail(df, loss_symbols):
    """Deep dive into strategy-level details for loss symbols."""
    sym_loss_df = df[df["mapped_symbol"].isin(loss_symbols)].copy()
    sym_strat_detail = build_group_summary(sym_loss_df, ["mapped_symbol", "strategy"])
    loss_sym_strats = filter_rows_below_threshold(
        sym_strat_detail,
        "npnl_r+un",
        THRESHOLDS["loss_pnl"],
    )
    return loss_sym_strats


def _generate_and_send_report(
    report_text, final_df, out_dir, recipient=None, group_id=None
):
    """Generate report files and send via Signal client."""
    text_path = save_report(report_text, out_dir)
    logger.info(f"Report text saved to: {text_path}")

    csv_path = save_csv(final_df, out_dir, prefix="")
    logger.info(f"CSV saved to: {csv_path}")

    png_path = net_pnl_to_png_styled(
        final_df, out_dir / "daily_net_pnl_by_strategy.png", highlight_col="npnl_r+un"
    )
    logger.info(f"PNG saved to: {png_path}")
    if not app_settings.enable_signal_notifications:
        return png_path, csv_path, text_path
    if recipient or group_id:
        try:
            client = SignalClient()
            send_kwargs = {"recipient": recipient, "group_id": group_id}
            client.send(report_text, attachments=png_path, **send_kwargs)
            logger.info("Report sent via Signal successfully.")
        except Exception as exc:
            logger.error(f"Failed to send Signal message: {exc}", exc_info=True)

    return png_path, csv_path, text_path


def main():
    logging.basicConfig(
        level=app_settings.log_level.upper(),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    try:
        file_path = app_settings.net_pnl_input_path
        logger.info(f"Loading data from: {file_path}")
        source = app_settings.source
        df = load_pnl_data(source, file_path)
    except FileNotFoundError:
        logger.error(f"CSV input file not found: {app_settings.net_pnl_input_path}")
        raise
    except Exception as exc:
        logger.error(f"Failed to load data: {exc}", exc_info=True)
        raise

    try:
        total_npnl = df["npnl_r+un"].sum()

        # Analyze base strategy losses
        loss_base_strats = _analyze_base_strategy_losses(df)

        # Build strategy summary table
        w_category_strat_sum_df = _build_strategy_summary_table(df)

        # Analyze symbol losses
        loss_sym_df, loss_symbols, severe_symbols = _analyze_symbol_losses(df)
        large_profit_symbols = _analyze_large_profit_symbols(df)

        # Build final table
        final_df = pd.concat(
            [
                w_category_strat_sum_df,
                loss_sym_df.rename(columns={"mapped_symbol": "strategy"}),
            ],
            ignore_index=True,
            sort=False,
        )

        # Deep dive into symbol-strategy details
        loss_sym_strats = _build_symbol_strategy_detail(df, loss_symbols)

        # Build report text
        report_text = build_daily_report(
            total_npnl,
            loss_base_strats,
            severe_symbols,
            large_profit_symbols,
            loss_symbols,
            loss_sym_strats,
        )
        logger.info("Report text built successfully.")
    except Exception as exc:
        logger.error(f"Failed to generate report: {exc}", exc_info=True)
        raise

    # Generate files and send — Signal failure is non-fatal and logged inside
    out_dir = Path(app_settings.output_dir) / "net_pnl"
    recipient = app_settings.signal_recipient
    group_id = app_settings.signal_group_id
    png_path, csv_path, text_path = _generate_and_send_report(
        report_text, final_df, out_dir, recipient, group_id
    )

    return report_text, png_path, csv_path, text_path


if __name__ == "__main__":
    main()
