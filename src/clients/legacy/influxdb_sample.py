from influxdb_client import InfluxDBClient
import os
import csv

print(os.environ.get("INFLUXDB_TOKEN"))
INFLUX_BUCKET = "test"
MEASUREMENT = "binance_ALTUSDT_ohlcv"


def get_ohlcv_data(client):
    query = f"""
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: 0)
        |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> limit(n:10)
    """

    query_api = client.query_api()
    tables = query_api.query(query)

    results = []

    for table in tables:
        for record in table.records:
            results.append(
                {
                    "time": record.get_time(),
                    "open": record.values.get("open"),
                    "high": record.values.get("high"),
                    "low": record.values.get("low"),
                    "close": record.values.get("close"),
                    "volume": record.values.get("volume"),
                    "exchange": record.values.get("exchange"),
                    "symbol": record.values.get("symbol"),
                }
            )

    return results


def write_to_csv(data):
    with open("ohlcv_output.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)

        # Header
        writer.writerow(
            ["time", "open", "high", "low", "close", "volume", "exchange", "symbol"]
        )

        # Rows
        for row in data:
            writer.writerow(
                [
                    row["time"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"],
                    row["exchange"],
                    row["symbol"],
                ]
            )


def main():
    client = InfluxDBClient(
        url="http://localhost:8086",
        token=os.environ.get("INFLUXDB_TOKEN"),
        org="Blackbird",
    )

    data = get_ohlcv_data(client)

    print(f"Fetched {len(data)} rows")

    write_to_csv(data)
    print("CSV written to ohlcv_output.csv")


if __name__ == "__main__":
    main()
