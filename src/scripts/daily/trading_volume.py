from src.utils.load_data import load_trading_volume_data
from src.utils.constants import REQUIREMENT_VOLUME
import pandas as pd


FINAL_ORDER = [
    "product",
    "base",
    "requirement",
    "average_up_to_date",
    "last_24h_usd_volume",
    "total_usd_volume",
    "days_since_listing",
    "remaining_days",
    "meets_requirement",
]

def analyze_trading_volume(df):
    # prepare data
    # group by base and sum usd_volume_24h, keep the earliest timestamp for each base token
    print(df)
    volume_summary = df.groupby(["product", "base"]).agg({
        "timestamp_utc": "min",
        "usd_volume_24h": "sum",
    }).reset_index().rename(columns={"usd_volume_24h": "total_usd_volume"})
    volume_summary["days_since_listing"] = (pd.to_datetime("now") - pd.to_datetime(volume_summary["timestamp_utc"])).dt.days + 1
    volume_summary["remaining_days"] = 14 - volume_summary["days_since_listing"]
    volume_summary['average_up_to_date'] = volume_summary['total_usd_volume'] / volume_summary['days_since_listing']
    # calculate last 24h volume
    last_24h_threshold = pd.to_datetime("now") - pd.Timedelta(days=1)
    last_24h_volume = df[df["timestamp_utc"] >= last_24h_threshold].groupby(["product", "base"])["usd_volume_24h"].sum().reset_index().rename(columns={"usd_volume_24h": "last_24h_usd_volume"})
    # merge with volume_summary
    volume_summary = volume_summary.merge(last_24h_volume, on=["product", "base"], how="left").fillna({"last_24h_usd_volume": 0})
    volume_summary.drop(columns=["timestamp_utc"], inplace=True)  # drop timestamp column as it's no longer needed after calculating days since listing])
    # add requirement volume
    # NOTE: if there are multiple exchanges in the future, we can add another layer of grouping by exchange, and the requirement volume can also be defined by exchange in the constants file
    exchange_requirement_volume = REQUIREMENT_VOLUME.get("kucoin")
    volume_summary["requirement"] = volume_summary.apply(
        lambda row: exchange_requirement_volume[row["base"]][row["product"]],
        axis=1
        )  # look up threshold by both base token and product type
    # exclude rows with requirement == 0
    volume_summary = volume_summary[volume_summary["requirement"] > 0]
    volume_summary["meets_requirement"] = volume_summary["average_up_to_date"] >= volume_summary["requirement"]

    # format final order of columns
    volume_summary = volume_summary[FINAL_ORDER].sort_values(["product", "base"]).reset_index(drop=True)
    return volume_summary


def main():
    df = load_trading_volume_data("local", "data/kucoin_24h_volume_summary_2026-04-13_04-48-18.csv")
    volume_summary = analyze_trading_volume(df)
    print(volume_summary)


if __name__ == "__main__":
    main()
