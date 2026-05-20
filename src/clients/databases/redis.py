from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

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

    def close(self) -> None:
        if self.execution_mode == "ssh":
            return None
        self._client.close()  # pyrefly: ignore

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
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"ssh redis action returned invalid JSON: {completed.stdout.strip()}"
            ) from exc


if __name__ == "__main__":
    client = RedisClient(execution_mode="ssh", ssh_host="T1_newuser1")
    try:
        spot_symbols = client.get_symbols_by_market("spot")
        perp_symbols = client.get_symbols_by_market("perp")
        print("spot_count", len(spot_symbols))
        print("spot_first_20", spot_symbols[:20])
        print("perp_count", len(perp_symbols))
        print("perp_first_20", perp_symbols[:20])
    finally:
        client.close()
