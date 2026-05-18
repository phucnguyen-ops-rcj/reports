from __future__ import annotations

import argparse
import json
import socket
from typing import Any

from redis.exceptions import RedisError

from src.clients.databases.redis import RedisClient, RedisConfig


def diagnose_connection(
    host: str,
    port: int,
    *,
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "host": host,
        "port": port,
        "dns": {"ok": False, "addresses": []},
        "tcp": {"ok": False, "error": None},
    }

    try:
        address_info = socket.getaddrinfo(
            host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
        addresses = sorted({item[4][0] for item in address_info})
        diagnostic["dns"] = {"ok": True, "addresses": addresses}
    except OSError as exc:
        diagnostic["dns"] = {"ok": False, "error": str(exc), "addresses": []}
        return diagnostic

    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            diagnostic["tcp"] = {"ok": True, "error": None}
    except OSError as exc:
        diagnostic["tcp"] = {"ok": False, "error": str(exc)}

    return diagnostic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a Redis instance.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--db", type=int, default=None)
    parser.add_argument("--match", default=None)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--sample-size", type=int, default=3)
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument(
        "--execution-mode",
        choices=["ssh", "local"],
        default=None,
        help="Run Redis commands locally or through SSH.",
    )
    parser.add_argument("--ssh-host", default=None)
    parser.add_argument("--ssh-workdir", default=None)
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> RedisConfig:
    defaults = RedisConfig.from_env()
    return RedisConfig(
        host=args.host or defaults.host,
        port=args.port if args.port is not None else defaults.port,
        username=args.username if args.username is not None else defaults.username,
        password=args.password if args.password is not None else defaults.password,
        db=args.db if args.db is not None else defaults.db,
        execution_mode=(
            args.execution_mode
            if args.execution_mode is not None
            else defaults.execution_mode
        ),
        ssh_host=args.ssh_host or defaults.ssh_host,
        ssh_workdir=args.ssh_workdir or defaults.ssh_workdir,
    )


def main() -> None:
    args = parse_args()
    config = build_config(args)

    payload: dict[str, Any] = {}
    if args.diagnose:
        payload["diagnostic"] = diagnose_connection(config.host, config.port)

    client = RedisClient(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        db=config.db,
        execution_mode=config.execution_mode,
        ssh_host=config.ssh_host,
        ssh_workdir=config.ssh_workdir,
    )
    try:
        info = client.info()
        payload.update(
            {
                "ping": client.ping(),
                "redis_version": info.get("redis_version"),
                "dbsize": client.dbsize(),
                "keys": client.scan_keys(match=args.match, limit=args.limit),
                "samples": client.sample_keys(
                    match=args.match,
                    limit=min(args.limit, 5),
                    sample_size=args.sample_size,
                ),
            }
        )
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    except RedisError as exc:
        payload["redis_error"] = str(exc)
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    finally:
        client.close()


if __name__ == "__main__":
    main()
