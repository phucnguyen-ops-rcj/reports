from __future__ import annotations

import json
import os
import shlex
import subprocess
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
        client: redis.Redis | Any | None = None,
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

    def _execute(self, action: str, **kwargs: Any) -> Any:
        if self.execution_mode == "ssh":
            return self._ssh_action(action, **kwargs)

        if action == "ping":
            return bool(self._client.ping())
        if action == "info":
            return dict(self._client.info())  # pyrefly: ignore
        if action == "dbsize":
            return int(self._client.dbsize())  # pyrefly: ignore
        if action == "exists":
            return bool(self._client.exists(kwargs["key"]))
        if action == "type":
            return str(self._client.type(kwargs["key"]))
        if action == "ttl":
            return int(self._client.ttl(kwargs["key"]))  # pyrefly: ignore
        if action == "scan_iter":
            return list(
                self._client.scan_iter(
                    match=kwargs.get("match"),
                    count=kwargs.get("count", 100),
                )
            )
        if action == "get":
            return self._client.get(kwargs["key"])
        if action == "hgetall":
            return dict(self._client.hgetall(kwargs["key"]))  # pyrefly: ignore
        if action == "lrange":
            return list(
                self._client.lrange(
                    kwargs["key"],
                    kwargs.get("start", 0),
                    kwargs.get("end", -1),
                )
            )  # pyrefly: ignore
        if action == "llen":
            return int(self._client.llen(kwargs["key"]))  # pyrefly: ignore
        if action == "zcard":
            return int(self._client.zcard(kwargs["key"]))  # pyrefly: ignore
        if action == "zrange":
            return list(
                self._client.zrange(
                    kwargs["key"],
                    kwargs.get("start", 0),
                    kwargs.get("end", -1),
                    withscores=kwargs.get("withscores", True),
                )
            )  # pyrefly: ignore
        if action == "ts_range":
            return list(
                self._client.execute_command(
                    "TS.RANGE",
                    kwargs["key"],
                    kwargs.get("from_ts", "-"),
                    kwargs.get("to_ts", "+"),
                )
            )

        raise ValueError(f"Unsupported redis action: {action}")

    def ping(self) -> bool:
        return bool(self._execute("ping"))

    def info(self) -> dict[str, Any]:
        return dict(self._execute("info"))

    def dbsize(self) -> int:
        return int(self._execute("dbsize"))

    def exists(self, key: str) -> bool:
        return bool(self._execute("exists", key=key))

    def key_type(self, key: str) -> str:
        return str(self._execute("type", key=key))

    def ttl(self, key: str) -> int:
        return int(self._execute("ttl", key=key))

    def scan_iter(self, match: str | None = None, count: int = 100) -> Iterator[str]:
        for key in self._execute("scan_iter", match=match, count=count):
            yield str(key)

    def scan_keys(
        self, *, match: str | None = None, limit: int = 100, count: int = 100
    ) -> list[str]:
        keys: list[str] = []
        for key in self.scan_iter(match=match, count=count):
            keys.append(str(key))  # pyrefly: ignore
            if len(keys) >= limit:
                break
        return keys

    def get(self, key: str) -> str | None:
        value = self._execute("get", key=key)
        return None if value is None else str(value)

    def hgetall(self, key: str) -> dict[str, Any]:
        return dict(self._execute("hgetall", key=key))

    def lrange(self, key: str, start: int = 0, end: int = -1) -> list[Any]:
        return list(self._execute("lrange", key=key, start=start, end=end))

    def zrange(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        *,
        withscores: bool = True,
    ) -> list[Any]:
        return list(
            self._execute(
                "zrange",
                key=key,
                start=start,
                end=end,
                withscores=withscores,
            )
        )

    def ts_range(
        self,
        key: str,
        from_ts: str | int = "-",
        to_ts: str | int = "+",
    ) -> list[list[Any]]:
        return list(self._execute("ts_range", key=key, from_ts=from_ts, to_ts=to_ts))

    def describe_key(self, key: str, *, sample_size: int = 10) -> dict[str, Any]:
        if not self.exists(key):
            return {"key": key, "exists": False}

        key_type = self.key_type(key)
        payload: dict[str, Any] = {
            "key": key,
            "exists": True,
            "type": key_type,
            "ttl": self.ttl(key),
        }

        if key_type == "string":
            payload["value"] = self.get(key)
            return payload

        if key_type == "hash":
            payload["value"] = self.hgetall(key)
            return payload

        if key_type == "list":
            payload["length"] = int(self._execute("llen", key=key))
            payload["sample"] = self.lrange(key, 0, max(sample_size - 1, 0))
            return payload

        if key_type == "zset":
            payload["length"] = int(self._execute("zcard", key=key))
            payload["sample"] = self.zrange(
                key, 0, max(sample_size - 1, 0), withscores=True
            )
            return payload

        payload["value"] = None
        return payload

    def sample_keys(
        self,
        *,
        match: str | None = None,
        limit: int = 10,
        sample_size: int = 10,
        count: int = 100,
    ) -> list[dict[str, Any]]:
        return [
            self.describe_key(key, sample_size=sample_size)
            for key in self.scan_keys(match=match, limit=limit, count=count)
        ]

    def close(self) -> None:
        if self.execution_mode == "ssh":
            return None
        self._client.close()

    def _ssh_action(self, action: str, **kwargs: Any) -> Any:
        payload = {
            "action": action,
            "connection": {
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "password": self.password,
                "db": self.db,
                "decode_responses": self.decode_responses,
            },
            "kwargs": kwargs,
        }
        remote_script = f"""
import json
import redis

payload = json.loads({json.dumps(json.dumps(payload))})
connection = payload["connection"]
kwargs = payload["kwargs"]
client = redis.Redis(**connection)
action = payload["action"]

if action == "ping":
    result = bool(client.ping())
elif action == "info":
    result = dict(client.info())
elif action == "dbsize":
    result = int(client.dbsize())
elif action == "exists":
    result = bool(client.exists(kwargs["key"]))
elif action == "type":
    result = str(client.type(kwargs["key"]))
elif action == "ttl":
    result = int(client.ttl(kwargs["key"]))
elif action == "scan_iter":
    result = list(client.scan_iter(match=kwargs.get("match"), count=kwargs.get("count", 100)))
elif action == "get":
    result = client.get(kwargs["key"])
elif action == "hgetall":
    result = dict(client.hgetall(kwargs["key"]))
elif action == "lrange":
    result = list(client.lrange(kwargs["key"], kwargs.get("start", 0), kwargs.get("end", -1)))
elif action == "llen":
    result = int(client.llen(kwargs["key"]))
elif action == "zcard":
    result = int(client.zcard(kwargs["key"]))
elif action == "zrange":
    result = list(client.zrange(kwargs["key"], kwargs.get("start", 0), kwargs.get("end", -1), withscores=kwargs.get("withscores", True)))
elif action == "ts_range":
    result = list(client.execute_command("TS.RANGE", kwargs["key"], kwargs.get("from_ts", "-"), kwargs.get("to_ts", "+")))
else:
    raise ValueError(f"Unsupported redis ssh action: {action}")

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
