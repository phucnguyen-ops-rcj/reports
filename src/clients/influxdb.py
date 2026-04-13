from __future__ import annotations

import logging
from influxdb_client import InfluxDBClient as _InfluxDBClient
from src.settings import get_settings
logger = logging.getLogger(__name__)


class InfluxDBClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, org: str | None = None) -> None:
        app_settings = get_settings()
        base_url = base_url.rstrip("/") if base_url else app_settings.influxdb_base_url.rstrip("/")
        token = token if token else app_settings.influxdb_token
        org = org if org else app_settings.influxdb_org
        self._client = _InfluxDBClient(url=base_url, token=token, org=org)

    def get_all_measurements(self, bucket) -> list[str]:
        """Return all measurement names in the configured bucket."""
        query = f'''
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{bucket}")
        '''
        query_api = self._client.query_api()
        tables = query_api.query(query)
        # each record's _value field holds the measurement name
        return [record.get_value() for table in tables for record in table.records]


if __name__ == "__main__":
    client = InfluxDBClient()
    measurements = client.get_all_measurements("test")
    print(measurements)