from __future__ import annotations

from src.clients.databases.redis import RedisClient


class FakeRedis:
    def ping(self):
        return True

    def info(self):
        return {"redis_version": "8.0.0"}

    def dbsize(self):
        return 4

    def exists(self, key: str):
        return key in {"plain", "hash", "items", "scores"}

    def type(self, key: str):
        return {
            "plain": "string",
            "hash": "hash",
            "items": "list",
            "scores": "zset",
        }[key]

    def ttl(self, key: str):
        return {"plain": 120, "hash": -1, "items": 60, "scores": 300}[key]

    def scan_iter(self, match=None, count=100):
        for key in ["plain", "hash", "items", "scores"]:
            yield key

    def get(self, key: str):
        return "hello"

    def hgetall(self, key: str):
        return {"field1": "value1", "field2": "value2"}

    def llen(self, key: str):
        return 3

    def lrange(self, key: str, start: int, end: int):
        return ["a", "b", "c"]

    def zcard(self, key: str):
        return 2

    def zrange(self, key: str, start: int, end: int, withscores: bool = False):
        return [("alice", 10.0), ("bob", 20.0)]

    def delete(self, *keys: str):
        return len(keys)

    def close(self):
        return None


def test_scan_keys_respects_limit():
    client = RedisClient(client=FakeRedis())
    assert client.scan_keys(limit=2) == ["plain", "hash"]


def test_describe_string_key():
    client = RedisClient(client=FakeRedis())
    assert client.describe_key("plain") == {
        "key": "plain",
        "exists": True,
        "type": "string",
        "ttl": 120,
        "value": "hello",
    }


def test_sample_keys_returns_typed_summaries():
    client = RedisClient(client=FakeRedis())
    samples = client.sample_keys(limit=4, sample_size=2)
    assert len(samples) == 4
    assert samples[1]["type"] == "hash"
    assert samples[2]["sample"] == ["a", "b", "c"]
    assert samples[3]["sample"] == [("alice", 10.0), ("bob", 20.0)]
