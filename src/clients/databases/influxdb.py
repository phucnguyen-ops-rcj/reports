from __future__ import annotations

import logging
import pandas as pd
from influxdb_client import InfluxDBClient as _InfluxDBClient
from src.settings import app_settings

logger = logging.getLogger(__name__)


class InfluxDBClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        org: str | None = None,
    ) -> None:
        base_url = (
            base_url.rstrip("/")
            if base_url
            else app_settings.influxdb_base_url.rstrip("/")
        )
        token = token if token else app_settings.influxdb_token
        org = org if org else app_settings.influxdb_org
        self._client = _InfluxDBClient(url=base_url, token=token, org=org)

    def get_all_measurements(self, bucket) -> list[str]:
        """Return all measurement names in the configured bucket."""
        query = f"""
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{bucket}")
        """
        query_api = self._client.query_api()
        tables = query_api.query(query)
        # each record's _value field holds the measurement name
        return [record.get_value() for table in tables for record in table.records]

    def get_order_book_imbalance_history(
        self,
        symbol: str,
        *,
        bucket: str = "test",
        days: int = 14,
        exchanges: tuple[str, ...] = ("binance", "kucoin"),
        imbalance_type: str = "max_level",
        field: str = "ask_bid_ratio",
        timezone: str | None = None,
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")
        if not exchanges:
            raise ValueError("exchanges must not be empty.")

        normalized_symbol = self._normalize_spot_symbol(symbol)
        tz_name = timezone or app_settings.tz
        exchange_filter = " or ".join(
            f'r.exchange == "{exchange}"' for exchange in exchanges
        )
        query = f"""
        from(bucket: "{bucket}")
          |> range(start: -{days + 2}d)
          |> filter(fn: (r) => r._measurement == "imbalance")
          |> filter(fn: (r) => r.symbol == "{normalized_symbol}")
          |> filter(fn: (r) => {exchange_filter})
          |> filter(fn: (r) => r.type == "{imbalance_type}")
          |> filter(fn: (r) => r._field == "{field}")
          |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
          |> keep(columns: ["_time", "_value", "exchange", "symbol", "type"])
        """
        query_api = self._client.query_api()
        tables = query_api.query(query)

        rows: list[dict[str, object]] = []
        for table in tables:
            for record in table.records:
                rows.append(
                    {
                        "time": pd.Timestamp(record.get_time()),
                        "value": float(record.get_value()),
                        "exchange": record.values.get("exchange"),
                        "symbol": record.values.get("symbol"),
                        "type": record.values.get("type"),
                    }
                )

        if not rows:
            return pd.DataFrame(columns=["date", "exchange", "value", "symbol", "type"])

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["date"] = (
            df["time"]
            .dt.tz_convert(tz_name)
            .dt.floor("D")
            .dt.tz_localize(None)  # pyrefly: ignore
        )
        daily_df = (
            df.groupby(["date", "exchange", "symbol", "type"], as_index=False)
            .agg(value=("value", "mean"))
            .sort_values(by=["date", "exchange"])
            .reset_index(drop=True)
        )
        return daily_df.tail(len(exchanges) * days)

    def get_aggregate_ohlcv_volume_history(
        self,
        measurement_names: list[str],
        *,
        bucket: str = "test",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")
        if not measurement_names:
            raise ValueError("measurement_names must not be empty.")

        start, stop = self._time_range_bounds(report_date, days=days, timezone=timezone)
        query_api = self._client.query_api()
        rows: list[dict[str, object]] = []

        for measurement_name in measurement_names:
            query = f"""
            from(bucket: "{bucket}")
              |> range(start: {start}, stop: {stop})
              |> filter(fn: (r) => r._measurement == "{measurement_name}")
              |> filter(fn: (r) => r._field == "volume")
              |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
              |> keep(columns: ["_time", "_value"])
            """
            tables = query_api.query(query)
            for table in tables:
                for record in table.records:
                    rows.append(
                        {
                            "measurement": measurement_name,
                            "time": pd.Timestamp(record.get_time()),
                            "value": float(record.get_value()),
                        }
                    )

        if not rows:
            return pd.DataFrame(columns=["date", "volume"])

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["date"] = (
            (df["time"].dt.tz_convert(timezone) - pd.Timedelta(days=1))
            # pyrefly: ignore
            .dt.floor("D")
            .dt.tz_localize(None)
        )
        return (
            df.groupby(["date"], as_index=False)
            .agg(volume=("value", "sum"))
            .sort_values(by="date")
            .reset_index(drop=True)
        )

    def get_ohlcv_history(
        self,
        measurement_name: str,
        *,
        bucket: str = "test",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")

        start, stop = self._time_range_bounds(report_date, days=days, timezone=timezone)
        query = f"""
        from(bucket: "{bucket}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r._measurement == "{measurement_name}")
          |> filter(fn: (r) => r._field == "open" or r._field == "high" or r._field == "low" or r._field == "close" or r._field == "volume")
          |> aggregateWindow(every: 1d, fn: last, createEmpty: false)
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> keep(columns: ["_time", "open", "high", "low", "close", "volume"])
        """
        query_api = self._client.query_api()
        tables = query_api.query(query)
        rows: list[dict[str, object]] = []
        for table in tables:
            for record in table.records:
                rows.append(
                    {
                        "time": pd.Timestamp(record.get_time()),
                        "open": record.values.get("open"),
                        "high": record.values.get("high"),
                        "low": record.values.get("low"),
                        "close": record.values.get("close"),
                        "volume": record.values.get("volume"),
                    }
                )

        if not rows:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume"]
            )

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["date"] = (
            (df["time"].dt.tz_convert(timezone) - pd.Timedelta(days=1))
            # pyrefly: ignore
            .dt.floor("D")
            .dt.tz_localize(None)
        )
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return (
            df.loc[:, ["date", "open", "high", "low", "close", "volume"]]
            .dropna(subset=["open", "high", "low", "close"])
            .sort_values(by="date")
            .reset_index(drop=True)
        )

    def get_ohlcv_volume_history(
        self,
        measurement_name: str,
        *,
        bucket: str = "test",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")

        start, stop = self._time_range_bounds(report_date, days=days, timezone=timezone)
        query = f"""
        from(bucket: "{bucket}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r._measurement == "{measurement_name}")
          |> filter(fn: (r) => r._field == "volume")
          |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
          |> keep(columns: ["_time", "_value"])
        """
        query_api = self._client.query_api()
        tables = query_api.query(query)
        rows: list[dict[str, object]] = []
        for table in tables:
            for record in table.records:
                rows.append(
                    {
                        "time": pd.Timestamp(record.get_time()),
                        "volume": float(record.get_value()),
                    }
                )

        if not rows:
            return pd.DataFrame(columns=["date", "volume"])

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["date"] = (
            (df["time"].dt.tz_convert(timezone) - pd.Timedelta(days=1))
            # pyrefly: ignore
            .dt.floor("D")
            .dt.tz_localize(None)
        )
        return (
            df.loc[:, ["date", "volume"]].sort_values(by="date").reset_index(drop=True)
        )

    def get_trade_notional_history(
        self,
        measurement_names: list[str],
        *,
        bucket: str = "Prod",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")
        if not measurement_names:
            raise ValueError("measurement_names must not be empty.")

        start, stop = self._time_range_bounds(report_date, days=days, timezone=timezone)
        query_api = self._client.query_api()
        rows: list[dict[str, object]] = []

        for measurement_name in measurement_names:
            query = f"""
            from(bucket: "{bucket}")
              |> range(start: {start}, stop: {stop})
              |> filter(fn: (r) => r._measurement == "{measurement_name}")
              |> filter(fn: (r) => r._field == "value")
              |> keep(columns: ["_time", "_value"])
            """
            tables = query_api.query(query)
            for table in tables:
                for record in table.records:
                    rows.append(
                        {
                            "measurement": measurement_name,
                            "time": pd.Timestamp(record.get_time()),
                            "value": abs(float(record.get_value())),
                        }
                    )

        if not rows:
            return pd.DataFrame(columns=["date", "measurement", "our_notional"])

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["date"] = (
            df["time"]
            .dt.tz_convert(timezone)
            .dt.floor("D")
            .dt.tz_localize(None)  # pyrefly: ignore
        )
        return (
            df.groupby(["date", "measurement"], as_index=False)
            .agg(our_notional=("value", "sum"))
            .sort_values(by=["date", "measurement"])
            .reset_index(drop=True)
        )

    def get_trade_buy_sell_notional_history(
        self,
        measurement_names: list[str],
        *,
        bucket: str = "Prod",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")
        if not measurement_names:
            raise ValueError("measurement_names must not be empty.")

        start, stop = self._time_range_bounds(report_date, days=days, timezone=timezone)
        query_api = self._client.query_api()
        rows: list[dict[str, object]] = []

        for measurement_name in measurement_names:
            query = f"""
            from(bucket: "{bucket}")
              |> range(start: {start}, stop: {stop})
              |> filter(fn: (r) => r._measurement == "{measurement_name}")
              |> filter(fn: (r) => r._field == "value" or r._field == "side")
              |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
              |> keep(columns: ["_time", "value", "side"])
            """
            tables = query_api.query(query)
            for table in tables:
                for record in table.records:
                    side = record.values.get("side")
                    value = record.values.get("value")
                    if side is None or value is None:
                        continue
                    rows.append(
                        {
                            "measurement": measurement_name,
                            "time": pd.Timestamp(record.get_time()),
                            "side": str(side).lower(),
                            "value": abs(float(value)),
                        }
                    )

        if not rows:
            return pd.DataFrame(columns=["date", "side", "notional"])

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["date"] = (
            df["time"]
            .dt.tz_convert(timezone)
            .dt.floor("D")
            .dt.tz_localize(None)  # pyrefly: ignore
        )
        return (
            df.groupby(["date", "side"], as_index=False)
            .agg(notional=("value", "sum"))
            .sort_values(by=["date", "side"])
            .reset_index(drop=True)
        )

    def get_trade_amount_history(
        self,
        measurement_names: list[str],
        *,
        bucket: str = "Prod",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")
        if not measurement_names:
            raise ValueError("measurement_names must not be empty.")

        start, stop = self._time_range_bounds(report_date, days=days, timezone=timezone)
        query_api = self._client.query_api()
        rows: list[dict[str, object]] = []

        for measurement_name in measurement_names:
            query = f"""
            from(bucket: "{bucket}")
              |> range(start: {start}, stop: {stop})
              |> filter(fn: (r) => r._measurement == "{measurement_name}")
              |> filter(fn: (r) => r._field == "amount")
              |> keep(columns: ["_time", "_value"])
            """
            tables = query_api.query(query)
            for table in tables:
                for record in table.records:
                    rows.append(
                        {
                            "measurement": measurement_name,
                            "time": pd.Timestamp(record.get_time()),
                            "value": abs(float(record.get_value())),
                        }
                    )

        if not rows:
            return pd.DataFrame(columns=["date", "measurement", "our_amount"])

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["date"] = (
            df["time"].dt.tz_convert(timezone).dt.floor("D").dt.tz_localize(None)
        )
        return (
            df.groupby(["date", "measurement"], as_index=False)
            .agg(our_amount=("value", "sum"))
            .sort_values(by=["date", "measurement"])
            .reset_index(drop=True)
        )

    def get_trade_buy_sell_amount_history(
        self,
        measurement_names: list[str],
        *,
        bucket: str = "Prod",
        days: int = 14,
        report_date: str | pd.Timestamp | None = None,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        if days <= 0:
            raise ValueError("days must be positive.")
        if not measurement_names:
            raise ValueError("measurement_names must not be empty.")

        start, stop = self._time_range_bounds(report_date, days=days, timezone=timezone)
        query_api = self._client.query_api()
        rows: list[dict[str, object]] = []

        for measurement_name in measurement_names:
            query = f"""
            from(bucket: "{bucket}")
              |> range(start: {start}, stop: {stop})
              |> filter(fn: (r) => r._measurement == "{measurement_name}")
              |> filter(fn: (r) => r._field == "amount" or r._field == "side")
              |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
              |> keep(columns: ["_time", "amount", "side"])
            """
            tables = query_api.query(query)
            for table in tables:
                for record in table.records:
                    side = record.values.get("side")
                    amount = record.values.get("amount")
                    if side is None or amount is None:
                        continue
                    rows.append(
                        {
                            "measurement": measurement_name,
                            "time": pd.Timestamp(record.get_time()),
                            "side": str(side).lower(),
                            "value": abs(float(amount)),
                        }
                    )

        if not rows:
            return pd.DataFrame(columns=["date", "side", "amount"])

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["date"] = (
            df["time"].dt.tz_convert(timezone).dt.floor("D").dt.tz_localize(None)
        )
        return (
            df.groupby(["date", "side"], as_index=False)
            .agg(amount=("value", "sum"))
            .sort_values(by=["date", "side"])
            .reset_index(drop=True)
        )

    @staticmethod
    def _time_range_bounds(
        report_date: str | pd.Timestamp | None,
        *,
        days: int,
        timezone: str,
    ) -> tuple[str, str]:
        if report_date is None:
            end_date = pd.Timestamp.now(tz=timezone).normalize()
        else:
            end_date = pd.Timestamp(report_date)
            if end_date.tzinfo is None:
                end_date = end_date.tz_localize(timezone)
            else:
                end_date = end_date.tz_convert(timezone)
            end_date = end_date.normalize()

        start_date = end_date - pd.Timedelta(days=days - 1)
        stop_date = end_date + pd.Timedelta(days=1)
        return start_date.tz_convert("UTC").isoformat(), stop_date.tz_convert(
            "UTC"
        ).isoformat()  # pyrefly: ignore

    @staticmethod
    def _normalize_spot_symbol(symbol: str) -> str:
        normalized = symbol.upper().replace("-", "/").replace("_", "/")
        if "/" in normalized:
            return normalized
        if normalized.endswith("USDT"):
            return f"{normalized[:-4]}/USDT"
        return f"{normalized}/USDT"


if __name__ == "__main__":
    client = InfluxDBClient()
    measurements = client.get_all_measurements("Prod")
    # print(measurements)
    df = client.get_trade_amount_history(["bybit_bybitcpp_ALT_USDT_trade"], days=20)
    print(df)
