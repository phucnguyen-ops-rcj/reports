# Mini Service API Reference

Use this as the shared reference for API conventions. Task-specific curl
templates live in the other docs.

Base endpoint: `http://18.176.93.228`

Authenticated requests require:

```bash
-H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
-H "Content-Type: application/json"
```

Do not hardcode bearer token values in docs or generated commands.

## Response Format

Most config endpoints return `text/plain`. Error responses are JSON.

Success for config endpoints:

```text
success
==================================================================
file: configcpp/...
==================================================================
[config content]
```

Success for JSON endpoints:

```json
{"code": 200, "message": "success", "request_id": "abc123"}
```

Error response:

```json
{"code": 400, "message": "Missing field: exchange", "request_id": "abc123"}
```

Keep `request_id` when asking admin to debug a failed request.

## HTTP Status Codes

| Code | Meaning | Action |
| --- | --- | --- |
| 200 | Success | Operation completed. |
| 400 | Bad request | Fix input and check `message`. |
| 401 | Unauthorized | Check the authorization header and token. |
| 403 | Forbidden | Token does not have access to the endpoint. |
| 404 | Not found | Resource does not exist or endpoint is misspelled. |
| 405 | Method not allowed | Use the correct HTTP method. |
| 409 | Conflict | Resource already exists; use update instead of setup. |
| 500 | Server error | Send `request_id` to admin. |
| 503 | Service unreachable | Server cannot reach downstream service; admin must investigate. |
| 504 | Service timed out | Retry or ask admin if it persists. |

## Common Errors

| Message | Meaning | Fix |
| --- | --- | --- |
| `unauthorized` | Bad or missing token. | Add `Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}`. |
| `forbidden` | Token is not allowed on this endpoint. | Use the correct token/access path. |
| `JSON object body required` | Missing or invalid JSON body. | Send valid JSON with `Content-Type: application/json`. |
| `Missing field: X` | Required field is missing. | Add field `X`. |
| `Invalid market 'X'` | Market is not valid. | Use `spot` or `perp`. |
| `Invalid tier 'X'` | Tier is not valid. | Use the tier values from the endpoint doc. |
| `Unknown exchange` | Exchange not supported. | Check supported exchanges below. |
| `Config not found` | Update/remove target does not exist. | Run the matching setup endpoint first. |
| `already exists` | Create target already exists. | Use the matching update endpoint. |
| `internal error` | Unexpected server error. | Send `request_id` to admin. |

## Supported Exchanges

Balance: `kc`, `kcf`, `kucoin`, `kucoinf`, `bybit`, `byb`, `okx`, `gate`,
`gateio`, `binance`, `bin`, `binf`, `binancef`, `bitget`, `mexc`, `fintrade`,
`fintradef`.

Arbitrage strategy: `kucoin`, `gate`, `binance`, `bybit`.

Stacker and new listing: `kucoin`, `binance`, `gate`, `bybit`.

## Endpoint Map

| Endpoint | Doc |
| --- | --- |
| `GET /health` | `ops_playbook.md` |
| `POST /get-balance` | `ops_playbook.md`, `accounts.md` |
| `POST /run-transfer` | `ops_playbook.md`, `accounts.md` |
| `POST /run-monitor` | `ops_playbook.md` |
| `POST /setup_new_listing_config` | `new_listing.md` |
| `POST /set_symbol_config` | `new_listing.md` |
| `POST /setup_new_listing_gateway` | `new_listing.md`, `gateway_inventory.md` |
| `POST /setup_listing_strategy_gateway_feed` | `new_listing.md` |
| `POST /setup_*_supervisorctl` | `new_listing.md` |
| `POST /feed_control` | `new_listing.md` |
| `POST /strategy_control` | `new_listing.md` |
| `POST /gateway_control` | `new_listing.md` |
| `POST /setup_stacker_config` | `stacker.md` |
| `POST /update_stacker_config` | `stacker.md` |
| Volume, 1s quoting, arbitrage, simple arbitrage, simple trader config endpoints | `strategy_configs.md` |
| Log, token availability, funding, position, market profile, fill diagnostics | `diagnostics.md` |
