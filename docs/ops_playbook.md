# Ops Curl Playbook

Use this file as a reference for generating commands only. Do not execute the
commands unless explicitly asked.

Base endpoint: `http://18.176.93.228`

Auth header:

```bash
-H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}"
```

## General Rules

- Return curl commands only.
- Do not include SSH wrappers.
- `token` is always uppercase, for example `usdt` becomes `USDT`.
- `exchange` must be one of the supported values listed per endpoint.
- `market` is required only for futures exchanges: `kcf`, `binf`, `fintradef`.
- If a required field is missing or ambiguous, ask for that field before
  returning a command.
- If the request does not match any endpoint, say so.
- For account aliases, check `docs/accounts.md`.
- For status codes and error response shape, check `docs/api_reference.md`.

## Endpoint 1 - GET /health

Use when asked: "is the server up", "health check", "ping the API".

```bash
curl http://18.176.93.228/health
```

## Endpoint 2 - POST /get-balance

Use when asked: "what's my balance", "check balance", "how much USDT do I have
on KuCoin".

Supported exchanges: `kc`, `kcf`, `kucoin`, `kucoinf`, `bybit`, `byb`, `okx`,
`gate`, `gateio`, `binance`, `bin`, `binf`, `binancef`, `bitget`, `mexc`,
`fintrade`, `fintradef`.

Required extraction:

- `exchange`: required. Ask "Which exchange?" if missing.
- `account`: optional, default `main`.
- `token`: optional, default `USDT`.
- `market`: required only for futures exchanges.
- Known account aliases are listed in `docs/accounts.md`.

Spot/default example:

```bash
curl -X POST http://18.176.93.228/get-balance \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"exchange": "kucoin", "account": "main", "token": "USDT"}'
```

Futures example:

```bash
curl -X POST http://18.176.93.228/get-balance \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"exchange": "kcf", "account": "main", "token": "USDT", "market": "perp"}'
```

## Endpoint 3 - POST /run-transfer

Use when asked: "transfer", "move funds", "withdraw", "sub to main",
"main to sub".

Supported modes:

| Mode | Description | Required extra fields |
| --- | --- | --- |
| `sub_to_main` | Sub-account to main | `sub_account_name` for `kc` |
| `main_to_sub` | Main to sub-account | `sub_account_name` for `kc` |
| `withdraw` | Withdraw to another exchange | `to_exchange` |
| `future_to_spot` | Futures to spot | `sub_account_name` for `kcf` |
| `spot_to_future` | Spot to futures | `sub_account_name` for `kcf` |
| `future_to_main` | Futures to main | `sub_account_name`, `kcf` only |
| `main_to_future` | Main to futures | `sub_account_name`, `kcf` only |
| `trading_to_funding` | Trading to funding | OKX only |

Required extraction:

- `mode`: required. Ask which mode if missing.
- `token`: required, uppercase.
- `from_exchange`: required.
- `amount`: required, positive number.
- `sub_account_name`: required for KuCoin sub-account and futures modes.
- `to_exchange`: required for `withdraw`.

Validation:

- `trading_to_funding` is OKX only.
- `future_to_main` and `main_to_future` are `kcf` only.

Basic example, no extra field:

```bash
curl -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode": "trading_to_funding", "token": "USDT", "from_exchange": "okx", "amount": 100}'
```

Sub-account example:

```bash
curl -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode": "sub_to_main", "token": "USDT", "from_exchange": "kc", "amount": 100, "sub_account_name": "ktfsmc15"}'
```

Futures example:

```bash
curl -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode": "spot_to_future", "token": "USDT", "from_exchange": "kcf", "amount": 100, "sub_account_name": "ktfsmc15"}'
```

Withdraw example:

```bash
curl -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode": "withdraw", "token": "USDT", "from_exchange": "kc", "amount": 100, "to_exchange": "bybit"}'
```

## Endpoint 4 - POST /run-monitor

Use when asked: "monitor", "show strategy", "stream monitor",
"watch positions".

`update_time` is optional. Use `10` when not provided.

Note: this streams SSE and stays open until interrupted.

```bash
curl -N -X POST http://18.176.93.228/run-monitor \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"update_time": 10}'
```
