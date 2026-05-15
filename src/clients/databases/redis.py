from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import redis

from src.settings import get_settings


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
        client: redis.Redis | Any | None = None,
    ) -> None:
        if client is not None:
            self._client = client
            return

        settings = get_settings()
        self._client = redis.Redis(
            host=host or settings.redis_host,
            port=port or settings.redis_port,
            username=username if username is not None else settings.redis_username,
            password=password if password is not None else settings.redis_password,
            db=db if db is not None else settings.redis_db,
            decode_responses=decode_responses,
        )

    def ping(self) -> bool:
        return bool(self._client.ping())

    def info(self) -> dict[str, Any]:
        return dict(self._client.info())

    def dbsize(self) -> int:
        return int(self._client.dbsize())

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def key_type(self, key: str) -> str:
        return str(self._client.type(key))

    def ttl(self, key: str) -> int:
        return int(self._client.ttl(key))

    def scan_iter(self, match: str | None = None, count: int = 100) -> Iterator[str]:
        return self._client.scan_iter(match=match, count=count)

    def scan_keys(
        self, *, match: str | None = None, limit: int = 100, count: int = 100
    ) -> list[str]:
        keys: list[str] = []
        for key in self.scan_iter(match=match, count=count):
            keys.append(str(key))
            if len(keys) >= limit:
                break
        return keys

    def get(self, key: str) -> str | None:
        value = self._client.get(key)
        return None if value is None else str(value)

    def set(
        self, key: str, value: str, *, ex: int | None = None, px: int | None = None
    ) -> bool:
        return bool(self._client.set(key, value, ex=ex, px=px))

    def delete(self, *keys: str) -> int:
        return int(self._client.delete(*keys))

    def hgetall(self, key: str) -> dict[str, Any]:
        return dict(self._client.hgetall(key))

    def lrange(self, key: str, start: int = 0, end: int = -1) -> list[Any]:
        return list(self._client.lrange(key, start, end))

    def zrange(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        *,
        withscores: bool = True,
    ) -> list[Any]:
        return list(self._client.zrange(key, start, end, withscores=withscores))

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
            payload["length"] = int(self._client.llen(key))
            payload["sample"] = self.lrange(key, 0, max(sample_size - 1, 0))
            return payload

        if key_type == "zset":
            payload["length"] = int(self._client.zcard(key))
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
        self._client.close()
