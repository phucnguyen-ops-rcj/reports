from __future__ import annotations

import json
import subprocess

from src.clients.databases.redis import RedisClient


class FakeRedis:
    def scan_iter(self, match=None, count=100):
        keys = [
            "KUC4:BTC:Spot:Buy",
            "KUC4:ETH:Spot:Sell",
            "BIN2:SOL:Future:NetRpnl",
            "BIN2:BTC:Future:NetUpnl",
            "invalid:key",
        ]
        market_token = None if match is None else match.split(":")[2]
        for key in keys:
            if market_token is None or f":{market_token}:" in key:
                yield key

    def close(self):
        return None


def test_get_symbols_by_market():
    client = RedisClient(client=FakeRedis())
    assert client.get_symbols_by_market("spot") == ["BTC", "ETH"]
    assert client.get_symbols_by_market("perp") == ["BTC", "SOL"]


def test_ssh_execution_mode_uses_remote_scan(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(["BIN2:SOL:Future:NetRpnl"]),
            stderr="",
        )

    monkeypatch.setattr("src.clients.databases.redis.subprocess.run", fake_run)
    client = RedisClient(
        host="172.31.33.22",
        port=6380,
        username="newuser1",
        password="secret",
        execution_mode="ssh",
        ssh_host="T1_newuser1",
        ssh_workdir="/remote/reports",
    )

    assert client.get_symbols_by_market("perp") == ["SOL"]
    ssh_args = captured["args"][0]
    assert ssh_args[:4] == ["ssh", "-q", "-T", "T1_newuser1"]
    assert "cd /remote/reports" in ssh_args[4]
    assert "172.31.33.22" in ssh_args[4]
    assert "*:*:Future:*" in ssh_args[4]
