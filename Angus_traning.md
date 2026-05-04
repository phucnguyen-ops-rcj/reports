# Mini Service API — User Guide

A complete guide for calling the Mini Service API.

---

## Getting Started

All requests go through the server. Contact admin for:
- The server URL
- Your Bearer token

Every authenticated request must include:
```
Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2
Content-Type: application/json
```

**Example:**
```bash
curl -X POST http://18.176.93.228/get-balance \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange": "kucoin", "account": "main", "token": "USDT"}'
```

> There are two token types. Your token determines which endpoints you can access — see the endpoint list for details.

---

## HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| **200** | Success | Operation completed |
| **400** | Bad request | Fix your input — check the `message` field |
| **401** | Unauthorized | Check your `Authorization` header / token |
| **403** | Forbidden | Your token does not have access to this endpoint |
| **404** | Not found | Resource doesn't exist (or endpoint typo) |
| **405** | Method not allowed | Wrong HTTP method (GET vs POST) |
| **409** | Conflict | Resource already exists (use update instead of setup) |
| **500** | Server error | Check with admin — server logs have details |
| **503** | Service unreachable | Server cannot reach the service — admin must investigate |
| **504** | Service timed out | Slow response — try again or contact admin |

---

## Response Format

Most config endpoints return **plain text** (`text/plain`). Error responses are always JSON.

**Success (plain text — config endpoints):**
```
✅ success
==================================================================
file: configcpp/...
==================================================================
[config content]
```

**Success (JSON — balance, transfer, health):**
```json
{"code": 200, "message": "success", "request_id": "abc123..."}
```

**Error (always JSON):**
```json
{"code": 400, "message": "Missing field: exchange", "request_id": "abc123..."}
```

The `request_id` is unique per request — give it to admin if you need help debugging.

---

## Common Error Messages

| Message | What It Means | How to Fix |
|---|---|---|
| `unauthorized` | Bad/missing token | Add `Authorization: Bearer <TOKEN>` header |
| `forbidden` | Token not allowed on this endpoint | Use the correct token for this endpoint |
| `JSON object body required` | No request body or invalid JSON | Send a valid JSON body |
| `Missing field: X` | Required field X is missing | Add field X to your payload |
| `Invalid market 'X'` | `market` value is not `spot` or `perp` | Use `"market": "spot"` or `"market": "perp"` |
| `Invalid tier 'X'` | `tier` value not valid | Use `"a"`, `"b"`, `"c"`, or `"s"` |
| `Unknown exchange '...'` | Exchange not supported | Check supported exchanges list below |
| `Config not found for X` | Symbol X has no config | Run `setup_*` first |
| `already exists` | Config already exists | Use `update_*` instead of `setup_*` |
| `check with admin` | Endpoint doesn't exist (typo) | Check endpoint URL |
| `internal error` | Unexpected server error | Send `request_id` to admin |

---

## Supported Exchanges

### get-balance
`kc`, `kcf`, `kucoin`, `kucoinf`, `bybit`, `byb`, `okx`, `gate`, `gateio`, `binance`, `bin`, `binf`, `binancef`, `bitget`, `mexc`, `fintrade`, `fintradef`

### Arbitrage strategy
`kucoin`, `gate`, `binance`, `bybit`

### Stacker / New listing
`kucoin`, `binance`, `gate`, `bybit`

---

## Endpoints

### 1. GET /health
No auth needed. Quick health check.

```bash
curl http://18.176.93.228/health
```
Response: `{"ok": true, "ts": 1776308962}`

---

### 2. POST /get-balance

Get balance for a specific account.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| exchange | string | yes | Exchange name (e.g. `kucoin`, `bybit`) |
| account | string | yes | `main`, `trading`, or sub-account alias |
| token | string | yes | Token symbol (e.g. `USDT`, `VSN`) |
| market | string | required for futures | `spot` or `perp` (only for `kcf`, `binf`, `fintradef`) |

**Examples:**
```bash
# KuCoin main account
curl -X POST http://18.176.93.228/get-balance \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange": "kucoin", "account": "main", "token": "USDT"}'

# KuCoin sub-account
curl -X POST http://18.176.93.228/get-balance \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange": "kc", "account": "colostrat1", "token": "USDT"}'

# KCF futures — perp balance
curl -X POST http://18.176.93.228/get-balance \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange": "kcf", "account": "perp_API_1_volume", "token": "USDT", "market": "perp"}'
```

**Response:** `{"code": 200, "balance": 1234.56, "exchange": "kc", "account": "main", "token": "USDT"}`

---

### 3. POST /run-transfer

bin (binance):
  fr

binf (binance future):
  fr

byb (bybit):
  fr

fintrade (fintrade):
  fintrade1
  fintrade2
  fintrade3
  fintrade4
  fintrade5

fintradef (fintrade future):
  fintrade1
  fintrade2
  fintrade3
  fintrade4
  fintrade5

gate (gate):
  fr

kc (kucoin):
 spotarb
 fdvstrat
 -vefrspot
  volumenewlisting
  liquidity
  spotinv
  mirroracc2
  colostrat1
  rfqhedge
  FR2

kcf (kucoin future):
  colostrat1
  perp_API_1_volume
  perp_API_2_volume
  perp_API_3_volume
  perp_API_4_volume
  perp_API_5_volume
  perp_API_6_volume


Move funds between accounts/exchanges.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| mode | string | yes | Transfer mode (see modes below) |
| token | string | yes | Token symbol |
| from_exchange | string | yes | Source exchange |
| amount | number | yes | Amount (positive number) |
| sub_account_name | string | required for kcf modes | Sub-account name |
| to_exchange | string | required for `withdraw` | Destination exchange |

**Modes:**
- `sub_to_main` — sub to main (kc requires `sub_account_name`)
- `main_to_sub` — main to sub (kc requires `sub_account_name`)
- `withdraw` — withdraw to another exchange (requires `to_exchange`)
- `future_to_spot` — futures to spot (kcf requires `sub_account_name`)
- `spot_to_future` — spot to futures (kcf requires `sub_account_name`)
- `future_to_main` — kcf only, requires `sub_account_name`
- `main_to_future` — kcf only, requires `sub_account_name`
- `trading_to_funding` — OKX only

**Example:**
```bash
curl -X POST http://18.176.93.228/run-transfer \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"mode": "sub_to_main", "token": "USDT", "from_exchange": "kc", "amount": 1, "sub_account_name": "mirroracc2"}'
```

---

### 4. POST /run-monitor

Stream the strategy monitor in real-time (SSE).

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| update_time | int | no | Refresh interval in seconds (default: 10) |

**Example:**
```bash
curl -N -X POST http://18.176.93.228/run-monitor \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"update_time": 10}'
```

`-N` flag keeps the connection open. Disconnect (Ctrl+C) to stop.

---

### 5. POST /setup_new_listing_config

Set up a new listing config.

**Payload (spot — needs all 16 fields):**
```bash
curl -X POST http://18.176.93.228/setup_new_listing_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "kucoin",
    "market": "spot",
    "symbol": "VSN-USDT",
    "strategy": "slow_mm",
    "tier": "c",
    "mode": "stacker",
    "hedge": "false",
    "auto_start": "true",
    "auto_restart": "true",
    "auto_config": "true",
    "model": "crossover_vol",
    "vol_param": "1.0",
    "trading_intensity_param": "1.0",
    "auto_start_ms": "1800000",
    "auto_restart_ms": "1209600000",
    "auto_config_ms": "1209600000"
  }'
```

**Payload (perp — only needs 4 fields):**
```bash
curl -X POST http://18.176.93.228/setup_new_listing_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "kucoin",
    "market": "perp",
    "symbol": "CHR-USDT",
    "strategy": "slow_mm"
  }'
```

**Valid values:**
- `market`: `spot`, `perp`
- `strategy`: `slow_mm`, `mid_mm`, `fast_mm`
- `tier`: `s`, `1`, `2`, `3` (spot only)
- `model`: `crossover_vol`, `kline_vol` (spot only)
- `mode`: `normal`, `stacker`

> If the symbol is not yet in market data, the response will include a note to call `/set_symbol_config` to register it first.

---

### 6. POST /setup_stacker_config

Configure stacker strategy (creates 1 feed + 4 gateway + 4 strategy files).

> **Ask admin for the correct `feed_host` and `gateway_host` values.**

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| exchanges | string | yes | `kucoin`, `binance`, `gate`, `bybit` |
| base_ccy | string | yes | Base currency (e.g. `RAVE`) |
| quote_ccy | string | yes | Quote currency (e.g. `USDT`) |
| market | string | no | `spot` (default) or `perp` |
| feed_host | string | yes | Full feed host:port — **ask admin** |
| gateway_host | string | yes | Full gateway host:port — **ask admin** |
| tick_size | number | yes | Price tick size |
| quantity_step_size | number | yes | Quantity step size |
| min_price | number | yes | Minimum price |
| max_price | number | yes | Maximum price |
| min_quantity | number | yes | Minimum order quantity |
| max_quantity | number | yes | Maximum order quantity |
| buy_stackers | string | yes | Proto-text stacker list: `[{price: X original_quantity: Y}, ...]` |
| sell_stackers | string | yes | Proto-text stacker list: `[{price: X original_quantity: Y}, ...]` |

**Example:**
```bash
curl -X POST http://18.176.93.228/setup_stacker_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "exchanges": "kucoin",
    "base_ccy": "RAVE",
    "quote_ccy": "USDT",
    "market": "spot",
    "feed_host": "0.0.0.0:41738",
    "gateway_host": "0.0.0.0:41799",
    "tick_size": 0.00001,
    "quantity_step_size": 0.01,
    "min_price": 0.00001,
    "max_price": 5.0,
    "min_quantity": 10.0,
    "max_quantity": 100000000000,
    "buy_stackers": "[{price: 0.0500 original_quantity: 1000},{price: 0.0499 original_quantity: 1000}]",
    "sell_stackers": "[{price: 0.0600 original_quantity: 1000},{price: 0.0601 original_quantity: 1000}]"
  }'
```

**Response:** plain text with file paths and all 4 strategy config previews (sensitive fields removed).

---

### 7. POST /update_stacker_config

Update an existing stacker config. Only fields you provide are changed.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| exchanges | string | yes | Exchange name (to identify the config) |
| base_ccy | string | yes | Base currency (to identify the config) |
| quote_ccy | string | yes | Quote currency (to identify the config) |
| feed_host | string | no | New feed host:port |
| gateway_host | string | no | New gateway host:port |
| tick_size | number | no | New price tick size |
| quantity_step_size | number | no | New quantity step size |
| min_price | number | no | New minimum price |
| max_price | number | no | New maximum price |
| min_quantity | number | no | New minimum order quantity |
| max_quantity | number | no | New maximum order quantity |
| buy_stackers | array | no | Full new buy list (replaces all existing) |
| sell_stackers | array | no | Full new sell list (replaces all existing) |

> At least one optional field must be provided. Must call `/setup_stacker_config` first.

**What configs are shown in the response:**

| Field(s) changed | feed shown | gateway shown | strategy shown |
|---|---|---|---|
| `max_price`, `tick_size`, etc. | yes | no | no |
| `feed_host` or `gateway_host` | yes | yes | yes (all 4) |
| `buy_stackers` or `sell_stackers` only | no | no | yes (all 4) |

> `buy_stackers` / `sell_stackers` are a **full replacement** — the new list replaces all existing orders across all 4 files.

**Example:**
```bash
curl -X POST http://18.176.93.228/update_stacker_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "exchanges": "kucoin",
    "base_ccy": "RAVE",
    "quote_ccy": "USDT",
    "max_price": 10.0
  }'
```

---

### 8. POST /start_volatility_model

Start a volatility model strategy.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| symbol | string | yes | `BASE-QUOTE` format |
| market | string | yes | `spot` or `perp` |
| exchange | string | yes | Exchange name |
| exchange_data | string | yes | Data source exchange |
| risk_tol | string | yes | `low`, `medium`, `high` |
| strategy | string | yes | `slow_mm`, `mid_mm`, `fast_mm` |

**Example:**
```bash
curl -X POST http://18.176.93.228/start_volatility_model \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "VSN-USDT", "market": "spot", "exchange": "kucoin", "exchange_data": "gate", "risk_tol": "low", "strategy": "slow_mm"}'
```

**Response:** plain text showing the model startup output (config updates, PID, log path).

---

### 9. POST /set_symbol_config

Write a symbol's market config.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| base_currency | string | yes | Base currency (e.g. `ARCSOL`) |
| quote_currency | string | yes | Quote currency (e.g. `USDT`) |
| market | string | yes | `spot` or `perp` |
| price_tick | number | yes | Minimum price increment |
| size_tick | number | yes | Minimum size increment |
| min_size | number | yes | Minimum order size |
| multiplier | number | yes | Contract multiplier (use `1` for spot) |
| contract_size | number | yes | Contract size (use `1` for spot) |
| first_date | number | yes | Listing timestamp in milliseconds |

**Example:**
```bash
curl -X POST http://18.176.93.228/set_symbol_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "base_currency": "ARCSOL",
    "quote_currency": "USDT",
    "market": "spot",
    "price_tick": 0.00001,
    "size_tick": 0.1,
    "min_size": 10,
    "multiplier": 1,
    "contract_size": 1,
    "first_date": 1735822800000
  }'
```

**Response:** stored config value.

---

### 10. POST /get_stacker_accepted_orders

Grep stacker strategy logs for accepted and rejected order responses.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| symbol | string | yes | `BASE-QUOTE`, `BASE_QUOTE`, or `BASE/QUOTE` format |
| date | string | no | Date in `YYYYMMDD` format (default: today) |

**Example:**
```bash
curl -X POST http://18.176.93.228/get_stacker_accepted_orders \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "MEGA-USDT", "date": "20260430"}'
```

**Response:** plain text, per log file (4 files total):
```
✅ success
==================================================================
kucoincpp_AI_USDT_twkpi_st_1.txtpb.INFO:
NEW_ORDER_STATUS_ACCEPTED = 24
OnGatewayMessage new_order_response { status: NEW_ORDER_STATUS_ACCEPTED order_id: 177... }
...
NEW_ORDER_STATUS_REJECTED = 2
OnGatewayMessage new_order_response { status: NEW_ORDER_STATUS_REJECTED order_id: 177... }
==================================================================
kucoincpp_AI_USDT_twkpi_st_2.txtpb.INFO:
...
```

> Rejected orders are deduplicated by `order_id` — the same order retried multiple times counts once.

---

### 11. Volume Strategy Config

#### POST /setup_volume_config

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| market | string | yes | `spot` or `perp` |
| tier | string | yes | `a`, `b`, `c`, or `s` |
| base_ccy | string | yes | Base currency |
| quote_ccy | string | yes | Quote currency |
| price_tick | number | yes | Price tick value |
| price_tick_size | number | yes | Price tick size |
| qty_unit | number | yes | Quantity unit |

```bash
curl -X POST http://18.176.93.228/setup_volume_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"market": "spot", "tier": "a", "base_ccy": "VSN", "quote_ccy": "USDT", "price_tick": 0.1, "price_tick_size": 0.01, "qty_unit": 0.0001}'
```

**Response:** plain text with file path and config contents (sensitive fields removed).

#### POST /update_volume_config

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| trade_symbol | string | yes | Format: `BASE-QUOTE` |
| market | string | yes | `spot` or `perp` |
| tier | string | no | If provided, reloads template |
| price_tick | number | no | Update price_tick |
| price_tick_size | number | no | Update price_tick_size |
| qty_unit | number | no | Update qty_unit |

```bash
curl -X POST http://18.176.93.228/update_volume_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"trade_symbol": "VSN-USDT", "market": "spot", "price_tick": 123.5}'
```

**Response:** plain text with file path and updated config contents (sensitive fields removed).

#### POST /remove_volume_strat_config

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| symbol | string | yes | Format: `BASE-QUOTE` |
| market | string | yes | `spot` or `perp` |

```bash
curl -X POST http://18.176.93.228/remove_volume_strat_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "VSN-USDT", "market": "spot"}'
```

---

### 12. 1s Quoting Config

#### POST /setup_1s_quoting_config

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| base_ccy | string | yes | Base currency |
| quote_ccy | string | yes | Quote currency |
| market | string | yes | `spot` or `perp` |

```bash
curl -X POST http://18.176.93.228/setup_1s_quoting_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "VSN", "quote_ccy": "USDT", "market": "spot"}'
```

**Response:** plain text showing config and strategy file contents (sensitive fields removed).

#### POST /update_1s_quoting_config

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| trade_symbol | string | yes | Format: `BASE-QUOTE` |
| market | string | yes | `spot` or `perp` |
| (any config field) | any | no | Any other field to update |

```bash
curl -X POST http://18.176.93.228/update_1s_quoting_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"trade_symbol": "VSN-USDT", "market": "spot", "max_position": 500}'
```

**Response:** plain text with updated config contents (sensitive fields removed).

#### POST /remove_1s_quoting_config

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| symbol | string | yes | Format: `BASE-QUOTE` |
| market | string | yes | `spot` or `perp` |

```bash
curl -X POST http://18.176.93.228/remove_1s_quoting_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "VSN-USDT", "market": "spot"}'
```

---

### 13. Arbitrage Strategy

#### POST /setup_arbitrage_strategy

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| exchanges | string | yes | Comma-separated: `kucoin`, `gate`, `binance`, `bybit` |
| base_ccy | string | yes | Comma-separated, must match exchange count |
| quote | string | yes | Comma-separated, must match exchange count |
| market | string | yes | `spot` or `perp` |
| taker_arb_min_bps | number | no | Default: 5 |
| maker_arb_min_bps | number | no | Default: 20000 |
| max_order_amount | number | no | Default: 50 |
| min_order_amount | number | no | Default: 20 |

```bash
curl -X POST http://18.176.93.228/setup_arbitrage_strategy \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchanges": "kucoin,gate", "base_ccy": "VSN,VSN", "quote": "USDT,USDT", "market": "spot"}'
```

**Response:** plain text with file path and config contents (sensitive fields removed).

#### POST /update_arbitrage_strategy

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| base_ccy | string | yes | Base currency of the existing config |
| market | string | yes | `spot` or `perp` |
| taker_arb_min_bps | number | no | |
| maker_arb_min_bps | number | no | |
| max_order_amount | number | no | |
| min_order_amount | number | no | |

```bash
curl -X POST http://18.176.93.228/update_arbitrage_strategy \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "VSN", "market": "spot", "taker_arb_min_bps": 120000}'
```

**Response:** plain text with updated fields list and config contents (sensitive fields removed).

#### POST /remove_arbitrage_strategy

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| base_ccy | string | yes | Base currency of the config to remove |
| market | string | yes | `spot` or `perp` |

```bash
curl -X POST http://18.176.93.228/remove_arbitrage_strategy \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "VSN", "market": "spot"}'
```

---

### 14. POST /setup_new_listing_gateway

Generate a gateway config file for a new listing.

> **Ask admin for `host`, `feed_host`, and `account_id` values.**

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| gateway_name | string | yes | Name for the generated file (no `.txtpb` extension) |
| market | string | yes | `spot` or `perp` |
| host | string | yes | Gateway host:port — **ask admin** |
| feed_host | string | yes | Feed host:port — **ask admin** |
| account_id | string | yes | Gateway account ID |
| exchange | string | no | Default: `kucoin` |

```bash
curl -X POST http://18.176.93.228/setup_new_listing_gateway \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "gateway_name": "emm_mirror_spot_gateway_custom_MULTITESTING1",
    "market": "spot",
    "host": "0.0.0.0:41799",
    "feed_host": "0.0.0.0:41738",
    "account_id": "TESTING1"
  }'
```

**Response:** plain text with file path and gateway config contents (sensitive fields removed).

---

### 15. POST /setup_listing_strategy_gateway_feed

Set up feed subscription and strategy config files for a new listing.

> **Ask admin for `feed_host` and `gateway_host`.**

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| base_ccy | string | yes | Base currency |
| quote_ccy | string | yes | Quote currency |
| market | string | yes | `spot` or `perp` |
| gateway_host | string | yes | **Ask admin** |
| feed_host | string | yes | **Ask admin** |

```bash
curl -X POST http://18.176.93.228/setup_listing_strategy_gateway_feed \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "VSN", "quote_ccy": "USDT", "market": "spot", "gateway_host": "0.0.0.0:41799", "feed_host": "0.0.0.0:41738"}'
```

**Response:** plain text with file paths, feed action note, and feed + strategy config previews.

---

### 16. Supervisor Config — New Listing

Register or remove programs in the supervisor config so processes can be managed via `supervisorctl`.

> **Ask admin for the correct `config_path` values.**

All setup endpoints return `409` if the program already exists. All remove endpoints return `404` if not found.

#### POST /setup_new_listing_gateway_supervisorctl

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| program_name | string | yes | Unique supervisor program name |
| config_path | string | yes | Full path to the gateway `.txtpb` config file |

```bash
curl -X POST http://18.176.93.228/setup_new_listing_gateway_supervisorctl \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"program_name": "mirror_spot_gateway_custom_BASEUSDT", "config_path": "<ask admin>"}'
```

#### POST /remove_new_listing_gateway_supervisorctl

```bash
curl -X POST http://18.176.93.228/remove_new_listing_gateway_supervisorctl \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"program_name": "mirror_spot_gateway_custom_BASEUSDT"}'
```

#### POST /setup_new_listing_feed_supervisorctl

```bash
curl -X POST http://18.176.93.228/setup_new_listing_feed_supervisorctl \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"program_name": "feed_spot_custom_kucoin_MULTI36", "config_path": "<ask admin>"}'
```

#### POST /remove_new_listing_feed_supervisorctl

```bash
curl -X POST http://18.176.93.228/remove_new_listing_feed_supervisorctl \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"program_name": "feed_spot_custom_kucoin_MULTI36"}'
```

#### POST /setup_new_listing_strategy_supervisorctl

```bash
curl -X POST http://18.176.93.228/setup_new_listing_strategy_supervisorctl \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"program_name": "mirror_spot_listings_strat2_VSNUSDT", "config_path": "<ask admin>"}'
```

#### POST /remove_new_listing_strategy_supervisorctl

```bash
curl -X POST http://18.176.93.228/remove_new_listing_strategy_supervisorctl \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"program_name": "mirror_spot_listings_strat2_VSNUSDT"}'
```

---

### 17. Process Control — feed, strategy, gateway

Start, stop, or restart a named supervisorctl process.

#### POST /feed_control
`name` must contain `feed`.

#### POST /strategy_control
`name` must contain `strat2`.

#### POST /gateway_control
`name` must contain `gateway`.

**Payload (all three):**
| Field | Type | Required | Description |
|---|---|---|---|
| method | string | yes | `start`, `stop`, or `restart` |
| name | string | yes | Supervisorctl program name |

```bash
curl -X POST http://18.176.93.228/feed_control \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"method": "start", "name": "feed_spot_custom_kucoin_MULTI36"}'
```

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "supervisorctl": {"rc": 0, "out": "feed_spot_custom_kucoin_MULTI36: started", "err": ""}
}
```

---

### 18. Simple Arbitrage Config

#### POST /setup_simple_arbitrage_config

Create a new simple arbitrage config file. Returns `409` if it already exists — use `/update_simple_arbitrage_config` instead.

**Top-level fields:**
| Field | Type | Required | Description |
|---|---|---|---|
| config_name | string | yes | Unique name for this config (alphanumeric + underscore) |
| params | object | yes | Config parameters (see below) |

**`params` — required fields:**
| Field | Type | Description |
|---|---|---|
| maker_exchange | string | Maker exchange (e.g. `binance`) |
| taker_exchange | string | Taker exchange (e.g. `binance`) |
| maker_market | string | `spot` or `perp` |
| taker_market | string | `spot` or `perp` |
| maker_side | string | Order side for maker: `buy` or `sell` |
| taker_side | string | Order side for taker: `buy` or `sell` |
| base_currency | string | Base currency (e.g. `KAT`) |
| quote_currency | string | Quote currency (e.g. `USDT`) |
| maker_time_in_force | string | TIF for maker orders (e.g. `GTC`) |
| taker_time_in_force | string | TIF for taker orders (e.g. `GTC`) |
| accumulation_mode | boolean | Enable accumulation mode |
| delta_threshold_usdt | number | Delta threshold in USDT |
| max_settle_size_usdt | number | Max settle size in USDT |
| maker_price_bps | number | Maker price offset in bps |
| update_portfolio_frequency_s | number | Portfolio update frequency (seconds) |
| update_order_frequency_s | number | Order update frequency (seconds) |
| hedge_price_bps | number | Hedge price offset in bps |
| max_position_size_usdt | number | Maximum position size in USDT |
| adjust_closing_taker_usdt | number | Closing taker adjustment in USDT |
| maker_fill_sleep | number | Sleep after maker fill (seconds) |
| taker_fill_sleep | number | Sleep after taker fill (seconds) |
| maker_min_order_size | number | Minimum maker order size in USDT |
| taker_min_order_size | number | Minimum taker order size in USDT |
| withdraw | boolean | Enable auto withdraw/transfer |

**`params` — optional fields:**
| Field | Type | Description |
|---|---|---|
| closing_mode | boolean | Enable closing mode |
| perp_closing_mode | boolean | Enable perp closing mode (when either market is `perp`) |
| auto_settlement | boolean | Enable auto settlement |

**`params` — conditional fields (when `withdraw` is `true`):**
| Field | Type | Description |
|---|---|---|
| maker_sub_to_main | boolean | Transfer maker sub-account → main before withdrawal |
| taker_main_to_sub | boolean | Transfer taker main → sub-account before deposit |
| transfer_from_exchange | string | Source exchange for transfer (e.g. `binance`) |
| transfer_to_exchange | string | Destination exchange (e.g. `binance`) |
| transfer_ccy | string | Currency to transfer (e.g. `KAT`) |
| transfer_wait_time_s | number | Wait time after transfer (seconds) |
| withdrawal_wait_time_s | number | Wait time after withdrawal (seconds) |
| deposit_amount_tolerance | number | Acceptable deposit shortfall (e.g. `0.02` = 2%) |
| chain | string | Blockchain network for withdrawal (e.g. `KATANA`, `ERC20`) |

```bash
curl -X POST http://18.176.93.228/setup_simple_arbitrage_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "my_arb_config",
    "params": {
      "maker_exchange": "binance",
      "taker_exchange": "okx",
      "maker_market": "spot",
      "taker_market": "perp",
      "maker_side": "buy",
      "taker_side": "sell",
      "base_currency": "KAT",
      "quote_currency": "USDT",
      "maker_time_in_force": "GTC",
      "taker_time_in_force": "GTC",
      "accumulation_mode": false,
      "closing_mode": false,
      "delta_threshold_usdt": 100,
      "max_settle_size_usdt": 100,
      "maker_price_bps": 0.0000,
      "update_portfolio_frequency_s": 5,
      "update_order_frequency_s": 10,
      "hedge_price_bps": 0.0005,
      "max_position_size_usdt": 200,
      "adjust_closing_taker_usdt": 30,
      "perp_closing_mode": false,
      "maker_fill_sleep": 10,
      "taker_fill_sleep": 10,
      "maker_min_order_size": 10,
      "taker_min_order_size": 15,
      "auto_settlement": true,
      "maker_sub_to_main": true,
      "taker_main_to_sub": true,
      "withdraw": true,
      "transfer_from_exchange": "okx",
      "transfer_to_exchange": "bin",
      "transfer_ccy": "KAT",
      "transfer_wait_time_s": 10,
      "withdrawal_wait_time_s": 10,
      "deposit_amount_tolerance": 0.02,
      "chain": ""
    }
  }'
```

**Response:**
```
✅ success
accumulation_mode : false
adjust_closing_taker_usdt : 30
auto_settlement : true
base_currency : "KAT"
chain : ""
closing_mode : false
delta_threshold_usdt : 100
deposit_amount_tolerance : 0.02
hedge_price_bps : 0.0005
maker_exchange : "binance"
maker_fill_sleep : 10
maker_market : "spot"
maker_min_order_size : 10
maker_price_bps : 0.0
maker_side : "buy"
maker_sub_to_main : true
maker_time_in_force : "GTC"
max_position_size_usdt : 200
max_settle_size_usdt : 100
perp_closing_mode : false
quote_currency : "USDT"
taker_exchange : "okx"
taker_fill_sleep : 10
taker_main_to_sub : true
taker_market : "perp"
taker_min_order_size : 15
taker_side : "sell"
taker_time_in_force : "GTC"
transfer_ccy : "KAT"
transfer_from_exchange : "okx"
transfer_to_exchange : "bin"
transfer_wait_time_s : 10
update_order_frequency_s : 10
update_portfolio_frequency_s : 5
withdraw : true
withdrawal_wait_time_s : 10
```

#### POST /update_simple_arbitrage_config

Update specific fields of an existing simple arbitrage config. Only the fields you provide in `params` are changed — everything else stays as-is. Returns `404` if the config doesn't exist.

> **Allowlist restriction:** This endpoint only allows updating the following config names. Any other `config_name` returns `403`:
> - `simple_arb_phuc_sp_pe_BNKC_FR_supervisor`
> - `simple_arb_phuc_sp_pe_BYBKC_FR_supervisor`
> - `simple_arb_phuc_sp_pe_GATKC_FR_supervisor`

**Top-level fields:**
| Field | Type | Required | Description |
|---|---|---|---|
| config_name | string | yes | Name of the existing config to update |
| params | object | yes | Any subset of the params fields above to update |

```bash
curl -X POST http://18.176.93.228/update_simple_arbitrage_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "phuc_spot_perp_closing_bin_bin",
    "params": {
      "maker_exchange": "binance",
      "taker_exchange": "okx",
      "maker_market": "spot",
      "taker_market": "perp",
      "maker_side": "buy",
      "taker_side": "sell",
      "base_currency": "KAT",
      "quote_currency": "USDT",
      "maker_time_in_force": "GTC",
      "taker_time_in_force": "GTC",
      "accumulation_mode": false,
      "closing_mode": false,
      "delta_threshold_usdt": 100,
      "max_settle_size_usdt": 100,
      "maker_price_bps": 0.0000,
      "update_portfolio_frequency_s": 5,
      "update_order_frequency_s": 10,
      "hedge_price_bps": 0.0005,
      "max_position_size_usdt": 200,
      "adjust_closing_taker_usdt": 30,
      "perp_closing_mode": false,
      "maker_fill_sleep": 10,
      "taker_fill_sleep": 10,
      "maker_min_order_size": 10,
      "taker_min_order_size": 15,
      "auto_settlement": true,
      "maker_sub_to_main": true,
      "taker_main_to_sub": true,
      "withdraw": true,
      "transfer_from_exchange": "okx",
      "transfer_to_exchange": "bin",
      "transfer_ccy": "KAT",
      "transfer_wait_time_s": 10,
      "withdrawal_wait_time_s": 10,
      "deposit_amount_tolerance": 0.02,
      "chain": ""
    }
  }'
```

**Response:**
```
✅ success
accumulation_mode : false
adjust_closing_taker_usdt : 30
auto_settlement : true
base_currency : "KAT"
chain : ""
closing_mode : false
delta_threshold_usdt : 100
deposit_amount_tolerance : 0.02
hedge_price_bps : 0.0005
maker_exchange : "binance"
maker_fill_sleep : 10
maker_market : "spot"
maker_min_order_size : 10
maker_price_bps : 0.0
maker_side : "buy"
maker_sub_to_main : true
maker_time_in_force : "GTC"
max_position_size_usdt : 200
max_settle_size_usdt : 100
perp_closing_mode : false
quote_currency : "USDT"
taker_exchange : "okx"
taker_fill_sleep : 10
taker_main_to_sub : true
taker_market : "perp"
taker_min_order_size : 15
taker_side : "sell"
taker_time_in_force : "GTC"
transfer_ccy : "KAT"
transfer_from_exchange : "okx"
transfer_to_exchange : "bin"
transfer_wait_time_s : 10
update_order_frequency_s : 10
update_portfolio_frequency_s : 5
withdraw : true
withdrawal_wait_time_s : 10
```

---

### 19. Simple Trader Config

#### POST /setup_simple_trader_config

Create a new simple trader config file. Returns `409` if it already exists — use `/update_simple_trader_config` instead.

**Top-level fields:**
| Field | Type | Required | Description |
|---|---|---|---|
| config_name | string | yes | Unique name for this config (alphanumeric + underscore) |
| params | object | yes | Config parameters (see below) |

**`params` — required fields:**
| Field | Type | Description |
|---|---|---|
| exchange | string | Exchange name (e.g. `kucoin`) |
| market | string | `spot` or `perp` |
| mode | string | `usdt` or `token` |
| base_currency | string | Base currency (e.g. `VSN`) |
| quote_currency | string | Quote currency (e.g. `USDT`) |
| maker_enabled | boolean | Enable maker orders |
| taker_enabled | boolean | Enable taker orders |
| side | string | Order side |
| max_position | number | Maximum position size |

**`params` — conditional fields:**
| Field | Type | Required when | Description |
|---|---|---|---|
| maker_min_order_size | number | `maker_enabled` is true | Minimum maker order size |
| taker_min_order_size | number | `taker_enabled` is true | Minimum taker order size |

```bash
curl -X POST http://18.176.93.228/setup_simple_trader_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "phuc_simple_trader",
    "params": {
      "exchange": "kucoin",
      "market": "spot",
    "mode": "token",
    "base_currency": "ABCDEFG",
    "quote_currency": "USDT",
    "maker_enabled": true,
    "taker_enabled": false,
    "side": "buy",
    "max_position": 100,
    "maker_price_bps": 1,
    "maker_order_distance_bps": 5,
    "taker_order_distance_bps": 5,
    "maker_min_order_size": 0.1,
    "taker_min_order_size": 1000,
    "maker_order_update_time_s": 10,
    "taker_order_update_time_s": 50,
    "information_update_time_s": 1,
    "time_sleep_after_fill_s": 10
    }
  }'
```

**Response:**
```
✅ success
exchange : "kucoin"
market : "spot"
mode : "usdt"
base_currency : "VSN"
quote_currency : "USDT"
maker_enabled : true
taker_enabled : false
side : "buy"
max_position : 1000
maker_min_order_size : 10
```

#### POST /update_simple_trader_config

Update specific fields of an existing simple trader config. Only the fields you provide in `params` are changed. Returns `404` if the config doesn't exist.

> **Allowlist restriction:** This endpoint only allows updating the following config names. Any other `config_name` returns `403`:
> - `simple_trade_phuc_pe_BN_FR_supervisor`
> - `simple_trade_phuc_pe_KC_FR_supervisor`
> - `simple_trade_phuc_sp_BN_FR_supervisor`
> - `simple_trade_phuc_sp_GAT_FR_supervisor`
> - `simple_trade_phuc_sp_KC_FR_supervisor`

**Top-level fields:**
| Field | Type | Required | Description |
|---|---|---|---|
| config_name | string | yes | Name of the existing config to update |
| params | object | yes | Any subset of the params fields above to update |

```bash
curl -X POST http://18.176.93.228/update_simple_trader_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "eth_arb_perp_withdraw",
    "params": {
      "exchange": "kucoin",
      "market": "spot",
    "mode": "token",
    "base_currency": "ABCDEFG",
    "quote_currency": "USDT",
    "maker_enabled": true,
    "taker_enabled": false,
    "side": "buy",
    "max_position": 100,
    "maker_price_bps": 1,
    "maker_order_distance_bps": 5,
    "taker_order_distance_bps": 5,
    "maker_min_order_size": 0.1,
    "taker_min_order_size": 1000,
    "maker_order_update_time_s": 10,
    "taker_order_update_time_s": 50,
    "information_update_time_s": 1,
    "time_sleep_after_fill_s": 10
    }
  }'
```

**Response:**
```
✅ success
exchange : "kucoin"
market : "spot"
mode : "usdt"
base_currency : "VSN"
quote_currency : "USDT"
maker_enabled : true
taker_enabled : false
side : "buy"
max_position : 1000
maker_min_order_size : 10
```

---

### 20. POST /get_token_chan_availability

Check deposit and withdrawal status for a token across all supported exchanges.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| token | string | yes | Token symbol (e.g. `"KAT"`) |

**Example:**
```bash
curl -X POST http://18.176.93.228/get_token_chan_availability \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"token": "KAT"}'
```

**Response:** plain text table showing deposit/withdrawal status per exchange and network:
```
exchange  token  network     deposit_enabled  withdraw_enabled
--------  -----  ----------  ---------------  ----------------
binance   KAT    BSC         False            False
binance   KAT    KATANA      True             True
bitget    KAT    KATANA      True             True
gateio    KAT    KAT         True             True
kucoin    KAT    KATANA      True             True
okx       KAT    KAT-KATANA  True             True
```

---

### 21. POST /get_funding_rate_snapshot

Get a funding rate snapshot for a token with 24-hour lookback and per-exchange history.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| token | string | yes | Token symbol (e.g. `"KAT"`) |

**Example:**
```bash
curl -X POST http://18.176.93.228/get_funding_rate_snapshot \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"token": "KAT"}'
```

**Response:** plain text funding rate snapshot:
```
Funding snapshot for KAT (24h lookback)
Updated: 2026-05-01 06:04:47 UTC

exch     next     int  cd        daily     next_ts
-------  -------  ---  --------  --------  -------------------
BINANCE  -0.012%  4h   01:55:12  -0.0730%  2026-05-01 08:00:00
BYBIT    0.005%   4h   01:55:12  0.0300%   2026-05-01 08:00:00

BINANCE KATUSDT
funding_time             rate         normalized_daily
-----------------------  -----------  ----------------
2026-04-30 08:00:00 UTC  0.00001652   0.0099%
```

---

### 22. POST /fetch_position_information

curl -X POST http://18.176.93.228/fetch_position_information \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"token": "KAT", "db": 53}'

**Response:** plain text PnL table (internal diagnostic lines hidden):
```
                   BINANCE:PERP:KATUSDT BINANCE:SPOT:KATUSDT ...
avg_price                0.012560215822       0.014054943887 ...
funding_fee                 9124.346958             0.000000 ...
pos                      1440123.000000       7137079.000000 ...
rpnl                        2669.907500            -0.000000 ...
```

---

### 23. POST /get_token_market_profile

Get a pacing envelope analysis — estimated daily capacity, completion time, and per-venue sizing for a given token and program size.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| token | string | yes | Token symbol (e.g. `"KAT"`) |
| order_size_token | number | yes | Program size in token units (e.g. `100000`) |

**Example:**
```bash
curl -X POST http://18.176.93.228/get_token_market_profile \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"token": "KAT", "order_size_token": 100000}'
```

**Response:** plain text pacing envelope analysis:
```
PACING ENVELOPE — KATUSDT
Base/Quote: KAT/USDT
Execution direction: SELL
Program size: 100,000.00 KAT

Estimated DAILY capacity (base units):
- LOW : 525,195.03
- MID : 2,413,936.04
- HIGH: 4,751,116.06

Per-venue (mid-cap sizing + execution daily capacity & split):
- Binance: cap_mid=1,000,711.43 ...
- OKX: cap_mid=14,471.60 ...
```

---

### 24. POST /get_volume_strategy_fills

Search volume strategy logs for fill events (`UPD_FILL`) for a given symbol.

**Payload:**
| Field | Type | Required | Description |
|---|---|---|---|
| base_currency | string | yes | Base currency (e.g. `"ASSET"`) |
| quote_currency | string | yes | Quote currency (e.g. `"USDT"`) |
| date | string | no | Date in `YYYYMMDD` format (default: today) |

**Example:**
```bash
curl -X POST http://18.176.93.228/get_volume_strategy_fills \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_currency": "ASSET", "quote_currency": "USDT", "date": "20260430"}'
```

**Response:** plain text with fill count and one fill line per row:
```
✅ success
symbol: ASSET:USDT  date: 20260430  fills: 4

UPD_FILL|KUCOIN_SPOT|BUY|ASSET:USDT|ordId:3083681437428899740|p:0.06208|sz:2484.5
UPD_FILL|KUCOIN_SECOND_SPOT|SELL|ASSET:USDT|ordId:3083681437053378460|p:0.06208|sz:2484.5
UPD_FILL|KUCOIN_SPOT|BUY|ASSET:USDT|ordId:3115610311245193116|p:0.06959|sz:1968
UPD_FILL|KUCOIN_SECOND_SPOT|SELL|ASSET:USDT|ordId:3115610311245193117|p:0.06959|sz:1968
```

---

## Common Workflows

### Workflow 1: Set up new listing
```bash
# 1. Register symbol config
curl -X POST http://18.176.93.228/set_symbol_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_currency":"NEW","quote_currency":"USDT","market":"perp","price_tick":0.0001,"size_tick":1,"min_size":1,"multiplier":1,"contract_size":1,"first_date":1735822800000}'

# 2. Create the listing config
curl -X POST http://18.176.93.228/setup_new_listing_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange":"kucoin","market":"perp","symbol":"NEW-USDT","strategy":"slow_mm"}'

# 3. Start volatility model
curl -X POST http://18.176.93.228/start_volatility_model \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NEW-USDT","market":"perp","exchange":"kucoin","exchange_data":"kucoin","risk_tol":"low","strategy":"slow_mm"}'
```

### Workflow 2: Set up volume strategy
```bash
# 1. Create config
curl -X POST http://18.176.93.228/setup_volume_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"market":"spot","tier":"a","base_ccy":"VSN","quote_ccy":"USDT","price_tick":0.1,"price_tick_size":0.01,"qty_unit":0.0001}'

# 2. Update params later
curl -X POST http://18.176.93.228/update_volume_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"trade_symbol":"VSN-USDT","market":"spot","price_tick":0.2}'

# 3. Remove when done
curl -X POST http://18.176.93.228/remove_volume_strat_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"VSN-USDT","market":"spot"}'
```

### Workflow 3: Check balances
```bash
# Main account
curl -X POST http://18.176.93.228/get-balance \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange":"kc","account":"main","token":"USDT"}'

# Sub-account
curl -X POST http://18.176.93.228/get-balance \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange":"kc","account":"colostrat1","token":"USDT"}'
```

### Workflow 4: Check stacker order status
```bash
# Check today's accepted/rejected orders for AI-USDT stacker
curl -X POST http://18.176.93.228/get_stacker_accepted_orders \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BILL-USDT"}'

# Check a specific date
curl -X POST http://18.176.93.228/get_stacker_accepted_orders \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BILL-USDT", "date": "20260504"}'
```

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---|---|---|
| `401 unauthorized` | Wrong/missing token | Check `Authorization: Bearer <TOKEN>` header |
| `403 forbidden` | Token not allowed on this endpoint | Use the correct token for this endpoint type |
| `404 check with admin` | Endpoint URL typo | Verify endpoint name spelling |
| `400 Missing field: market` | Forgot to pass `market` | Add `"market": "spot"` or `"market": "perp"` |
| `404 Config not found` | Trying to update/remove non-existent config | Run `setup_*` first |
| `409 already exists` | Trying to create duplicate | Use `update_*` instead |
| `500 internal error` | Server error | Send `request_id` to admin |
| `503 Service unreachable` | Cannot reach the service | Tell admin |
| `504 Service timed out` | Exchange API slow | Retry, or tell admin if persists |

---

## Getting Help

When asking admin for help, always include:
1. The full `curl` command you ran (redact any sensitive values)
2. The complete response (with `request_id` for JSON errors)
3. Approximate time of the request

Example:
> "I called `/setup_volume_config` at 14:30 with `request_id=abc123def456` and got `{"code": 500, "message": "internal error"}`. Can you check?"
