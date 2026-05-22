from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

import redis


@dataclass(frozen=True)
class RedisConfig:
    host: str = "172.31.33.22"
    port: int = 6380
    username: str | None = "newuser1"
    password: str | None = None
    db: int = 0
    execution_mode: Literal["ssh", "local"] = "ssh"
    ssh_host: str = "T1_newuser1"
    ssh_workdir: str = "/home/newuser1/work/new_project/training/reports"

    @classmethod
    def from_env(cls) -> RedisConfig:
        return cls(
            host=cls.host,
            port=cls.port,
            username=cls.username,
            password=os.environ.get("REDISCLI_AUTH") or cls.password,
            db=cls.db,
            execution_mode=cls.execution_mode,
            ssh_host=cls.ssh_host,
            ssh_workdir=cls.ssh_workdir,
        )


class RedisClient:
    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        db: int | None = None,
        decode_responses: bool = True,
        execution_mode: Literal["ssh", "local"] | None = None,
        ssh_host: str | None = None,
        ssh_workdir: str | None = None,
        client: redis.Redis | object | None = None,
    ) -> None:
        config = RedisConfig.from_env()
        self.execution_mode = (
            execution_mode if execution_mode is not None else config.execution_mode
        )
        self.ssh_host = ssh_host or config.ssh_host
        self.ssh_workdir = ssh_workdir or config.ssh_workdir
        self.host = host or config.host
        self.port = port if port is not None else config.port
        self.username = username if username is not None else config.username
        self.password = password if password is not None else config.password
        self.db = db if db is not None else config.db
        self.decode_responses = decode_responses

        if client is not None:
            self.execution_mode = "local"
            self._client = client
            return

        self._client = redis.Redis(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            db=self.db,
            decode_responses=decode_responses,
        )

    def _scan_iter(self, match: str | None = None, count: int = 100) -> Iterator[str]:
        if self.execution_mode == "ssh":
            keys = self._ssh_scan(match=match, count=count)
        else:
            keys = self._client.scan_iter(match=match, count=count)  # pyrefly: ignore

        for key in keys:
            yield str(key)

    def get_symbols_by_market(self, market: Literal["spot", "perp"]) -> list[str]:
        market_token = "Spot" if market == "spot" else "Future"
        symbols = {
            parts[1]
            for key in self._scan_iter(match=f"*:*:{market_token}:*", count=1000)
            if len((parts := str(key).split(":"))) == 4  # pyrefly: ignore
        }
        return sorted(symbols)

    def get_strategy_metrics_for_market_symbol(
        self,
        market: Literal["spot", "perp"],
        symbol: str,
        period_ms: int | None = None,
    ) -> dict[str, dict[str, Any]]:
        market_token = "Spot" if market == "spot" else "Future"
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must contain at least one non-empty character.")
        if period_ms is not None and period_ms <= 0:
            raise ValueError("period_ms must be greater than zero.")

        match = f"*:{normalized_symbol}:{market_token}:*"
        from_ts = "-" if period_ms is None else int(time.time() * 1000) - period_ms
        to_ts: int | str = "+"
        if self.execution_mode == "ssh":
            return self._ssh_get_strategy_metrics_for_market_symbol(
                match=match,
                symbol=normalized_symbol,
                market_token=market_token,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        return self._local_get_strategy_metrics_for_market_symbol(
            match=match,
            symbol=normalized_symbol,
            market_token=market_token,
            from_ts=from_ts,
            to_ts=to_ts,
        )

    def close(self) -> None:
        if self.execution_mode == "ssh":
            return None
        self._client.close()  # pyrefly: ignore

    def _local_get_strategy_metrics_for_market_symbol(
        self,
        *,
        match: str,
        symbol: str,
        market_token: str,
        from_ts: int | str,
        to_ts: int | str,
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for key in self._client.scan_iter(match=match, count=1000):  # pyrefly: ignore
            key_str = str(key)
            parts = key_str.split(":")
            if len(parts) != 4:
                continue
            strategy, key_symbol, key_market, metric = parts
            if key_symbol != symbol or key_market != market_token:
                continue
            strategy_metrics = result.setdefault(strategy, {})
            strategy_metrics[metric] = self._read_metric_payload(
                key_str, from_ts=from_ts, to_ts=to_ts
            )
        return dict(sorted(result.items()))

    def _read_metric_payload(
        self,
        key: str,
        *,
        from_ts: int | str,
        to_ts: int | str,
    ) -> dict[str, Any]:
        key_type = str(self._client.type(key))  # pyrefly: ignore
        if key_type == "TSDB-TYPE":
            values = self._client.execute_command(  # pyrefly: ignore
                "TS.RANGE",
                key,
                from_ts,
                to_ts,
            )
            return self._summarize_time_series(values)
        if key_type == "zset":
            values = self._client.zrange(key, 0, -1, withscores=True)  # pyrefly: ignore
            return self._summarize_sorted_set(values)
        if key_type == "string":
            return {"type": key_type, "value": self._client.get(key)}  # pyrefly: ignore
        if key_type == "hash":
            return {
                "type": key_type,
                "value": self._client.hgetall(key),
            }  # pyrefly: ignore
        if key_type == "list":
            return {
                "type": key_type,
                "value": self._client.lrange(key, 0, -1),
            }  # pyrefly: ignore
        if key_type == "set":
            return {
                "type": key_type,
                "value": sorted(list(self._client.smembers(key))),  # pyrefly: ignore
            }
        return {"type": key_type}

    def _ssh_get_strategy_metrics_for_market_symbol(
        self,
        *,
        match: str,
        symbol: str,
        market_token: str,
        from_ts: int | str,
        to_ts: int | str,
    ) -> dict[str, dict[str, Any]]:
        payload = {
            "connection": {
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "password": self.password,
                "db": self.db,
                "decode_responses": self.decode_responses,
            },
            "match": match,
            "symbol": symbol,
            "market_token": market_token,
            "from_ts": from_ts,
            "to_ts": to_ts,
        }
        remote_script = """
import json
import redis


def parse_numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_sorted_set(values):
    summary = {
        "type": "zset",
        "count": len(values),
        "points": values,
    }
    if not values:
        return summary

    first_member, first_score = values[0]
    last_member, last_score = values[-1]
    first_numeric = parse_numeric(first_member)
    last_numeric = parse_numeric(last_member)
    summary.update(
        {
            "first_member": first_member,
            "first_score": first_score,
            "last_member": last_member,
            "last_score": last_score,
            "first_numeric": first_numeric,
            "last_numeric": last_numeric,
            "delta": (
                None
                if first_numeric is None or last_numeric is None
                else last_numeric - first_numeric
            ),
        }
    )
    return summary


def summarize_time_series(values):
    points = []
    for timestamp, value in values:
        points.append([timestamp, value])

    summary = {
        "type": "TSDB-TYPE",
        "count": len(points),
        "points": points,
    }
    if not points:
        return summary

    first_timestamp, first_value = points[0]
    last_timestamp, last_value = points[-1]
    first_numeric = parse_numeric(first_value)
    last_numeric = parse_numeric(last_value)
    summary.update(
        {
            "first_timestamp": first_timestamp,
            "first_value": first_value,
            "last_timestamp": last_timestamp,
            "last_value": last_value,
            "first_numeric": first_numeric,
            "last_numeric": last_numeric,
            "delta": (
                None
                if first_numeric is None or last_numeric is None
                else last_numeric - first_numeric
            ),
        }
    )
    return summary


payload = json.loads(__PAYLOAD__)
client = redis.Redis(**payload["connection"])
result = {}
for key in client.scan_iter(match=payload["match"], count=1000):
    key_str = str(key)
    parts = key_str.split(":")
    if len(parts) != 4:
        continue
    strategy, symbol, market_token, metric = parts
    if symbol != payload["symbol"] or market_token != payload["market_token"]:
        continue

    key_type = client.type(key_str)
    if key_type == "zset":
        value = summarize_sorted_set(client.zrange(key_str, 0, -1, withscores=True))
    elif key_type == "TSDB-TYPE":
        value = summarize_time_series(
            client.execute_command(
                "TS.RANGE",
                key_str,
                payload["from_ts"],
                payload["to_ts"],
            )
        )
    elif key_type == "string":
        value = {"type": key_type, "value": client.get(key_str)}
    elif key_type == "hash":
        value = {"type": key_type, "value": client.hgetall(key_str)}
    elif key_type == "list":
        value = {"type": key_type, "value": client.lrange(key_str, 0, -1)}
    elif key_type == "set":
        value = {"type": key_type, "value": sorted(list(client.smembers(key_str)))}
    else:
        value = {"type": key_type}

    strategy_metrics = result.setdefault(strategy, {})
    strategy_metrics[metric] = value

print(json.dumps(dict(sorted(result.items())), default=str))
"""
        output = self._run_ssh_python(
            remote_script.replace("__PAYLOAD__", json.dumps(json.dumps(payload)))
        )
        return json.loads(output)

    def _summarize_sorted_set(self, values: list[tuple[Any, Any]]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "type": "zset",
            "count": len(values),
            "points": values,
        }
        if not values:
            return summary

        first_member, first_score = values[0]
        last_member, last_score = values[-1]
        first_numeric = self._parse_numeric(first_member)
        last_numeric = self._parse_numeric(last_member)
        summary.update(
            {
                "first_member": first_member,
                "first_score": first_score,
                "last_member": last_member,
                "last_score": last_score,
                "first_numeric": first_numeric,
                "last_numeric": last_numeric,
                "delta": (
                    None
                    if first_numeric is None or last_numeric is None
                    else last_numeric - first_numeric
                ),
            }
        )
        return summary

    def _summarize_time_series(self, values: list[list[Any]]) -> dict[str, Any]:
        points = [[timestamp, value] for timestamp, value in values]
        summary: dict[str, Any] = {
            "type": "TSDB-TYPE",
            "count": len(points),
            "points": points,
        }
        if not points:
            return summary

        first_timestamp, first_value = points[0]
        last_timestamp, last_value = points[-1]
        first_numeric = self._parse_numeric(first_value)
        last_numeric = self._parse_numeric(last_value)
        summary.update(
            {
                "first_timestamp": first_timestamp,
                "first_value": first_value,
                "last_timestamp": last_timestamp,
                "last_value": last_value,
                "first_numeric": first_numeric,
                "last_numeric": last_numeric,
                "delta": (
                    None
                    if first_numeric is None or last_numeric is None
                    else last_numeric - first_numeric
                ),
            }
        )
        return summary

    def _run_ssh_python(self, remote_script: str) -> str:
        shell_script = f"""
cd {shlex.quote(self.ssh_workdir)}
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python - <<'PY'
{remote_script}
PY
fi
exec python3 - <<'PY'
{remote_script}
PY
"""
        completed = subprocess.run(
            ["ssh", "-q", "-T", self.ssh_host, shell_script],
            capture_output=True,
            check=False,
            encoding="utf-8",
            timeout=30,
        )
        if completed.returncode != 0:
            body = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                f"ssh redis action failed with exit {completed.returncode}: {body}"
            )
        return completed.stdout

    @staticmethod
    def _parse_numeric(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _ssh_scan(self, *, match: str | None = None, count: int = 100) -> list[str]:
        payload = {
            "connection": {
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "password": self.password,
                "db": self.db,
                "decode_responses": self.decode_responses,
            },
            "match": match,
            "count": count,
        }
        remote_script = f"""
import json
import redis

payload = json.loads({json.dumps(json.dumps(payload))})
connection = payload["connection"]
client = redis.Redis(**connection)
result = list(client.scan_iter(match=payload.get("match"), count=payload.get("count", 100)))
print(json.dumps(result, default=str))
"""
        try:
            return json.loads(self._run_ssh_python(remote_script))
        except json.JSONDecodeError as exc:
            raise RuntimeError("ssh redis action returned invalid JSON.") from exc


if __name__ == "__main__":
    client = RedisClient(execution_mode="ssh", ssh_host="T1_newuser1")
    try:
        # spot_symbols = client.get_symbols_by_market("spot")
        # perp_symbols = client.get_symbols_by_market("perp")
        # print("spot_count", len(spot_symbols))
        # print("spot_first_20", spot_symbols[:20])
        # print("perp_count", len(perp_symbols))
        # print("perp_first_20", perp_symbols[:20])
        print(
            json.dumps(
                client.get_strategy_metrics_for_market_symbol("spot", "BTC"),
                indent=2,
            )
        )
    finally:
        client.close()
