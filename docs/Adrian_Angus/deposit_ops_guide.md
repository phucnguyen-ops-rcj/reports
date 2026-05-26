# Mini Service API — User Guide

A complete guide for calling the Mini Service API.

---

## Getting Started

All requests go through the server. Contact admin for:

- The server URL: http://18.176.93.228
- Your Bearer token: 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2

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

| Code          | Meaning             | Action                                                    |
| ------------- | ------------------- | --------------------------------------------------------- |
| **200** | Success             | Operation completed                                       |
| **400** | Bad request         | Fix your input — check the `message` field             |
| **401** | Unauthorized        | Check your `Authorization` header / token               |
| **403** | Forbidden           | Your token does not have access to this endpoint          |
| **404** | Not found           | Resource doesn't exist (or endpoint typo)                 |
| **405** | Method not allowed  | Wrong HTTP method (GET vs POST)                           |
| **409** | Conflict            | Resource already exists (use update instead of setup)     |
| **500** | Server error        | Check with admin — server logs have details              |
| **503** | Service unreachable | Server cannot reach the service — admin must investigate |
| **504** | Service timeout     | Slow response — try again or contact admin               |

---

## Response Format

All responses are JSON.

**Success:**

```json
{
  "code": 200,
  "message": "success",
  "request_id": "abc123..."
}
```

**Error:**

```json
{
  "code": 400,
  "message": "Missing field: exchange",
  "request_id": "abc123..."
}
```

The `request_id` is unique per request — give it to admin if you need help debugging.

---

## Common Error Messages

| Message                       | What It Means                                | How to Fix                                       |
| ----------------------------- | -------------------------------------------- | ------------------------------------------------ |
| `unauthorized`              | Bad/missing token                            | Add `Authorization: Bearer <TOKEN>` header     |
| `forbidden`                 | Token not allowed on this endpoint           | Use the correct token for this endpoint          |
| `JSON object body required` | No request body or invalid JSON              | Send a valid JSON body                           |
| `Missing field: X`          | Required field X is missing                  | Add field X to your payload                      |
| `Invalid market 'X'`        | `market` value is not `spot` or `perp` | Use `"market": "spot"` or `"market": "perp"` |
| `Invalid tier 'X'`          | `tier` value not valid                     | Use `"a"`, `"b"`, `"c"`, or `"s"`        |
| `Unknown exchange '...'`    | Exchange not supported                       | Check supported exchanges list below             |
| `Config not found for X`    | Symbol X has no config                       | Run `setup_*` first                            |
| `already exists`            | Config already exists                        | Use `update_*` instead of `setup_*`          |
| `check with admin`          | Endpoint doesn't exist (typo)                | Check endpoint URL                               |
| `internal error`            | Unexpected server error                      | Send `request_id` to admin                     |

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

| Field    | Type   | Required             | Description                                                      |
| -------- | ------ | -------------------- | ---------------------------------------------------------------- |
| exchange | string | yes                  | Exchange name (e.g.`kucoin`, `bybit`)                        |
| account  | string | yes                  | `main`, `trading`, or sub-account alias                      |
| token    | string | yes                  | Token symbol (e.g.`USDT`, `BTC`)                             |
| market   | string | required for futures | `spot` or `perp` (only for `kcf`, `binf`, `fintradef`) |

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

# KCF futures — spot balance
curl -X POST http://18.176.93.228/get-balance \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange": "kcf", "account": "colostrat1", "token": "USDT", "market": "spot"}'

# KCF futures — perp balance
curl -X POST http://18.176.93.228/get-balance \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchange": "kcf", "account": "colostrat1", "token": "USDT", "market": "perp"}'
```

**Response:** `{"code": 200, "balance": 1234.56, "exchange": "kc", "account": "main", "token": "USDT"}`

---

### 3. POST /run-transfer

Move funds between accounts/exchanges.

**Payload:**

| Field            | Type   | Required                  | Description                     |
| ---------------- | ------ | ------------------------- | ------------------------------- |
| mode             | string | yes                       | Transfer mode (see modes below) |
| token            | string | yes                       | Token symbol                    |
| from_exchange    | string | yes                       | Source exchange                 |
| amount           | number | yes                       | Amount (positive number)        |
| sub_account_name | string | required for kcf modes    | Sub-account name                |
| to_exchange      | string | required for `withdraw` | Destination exchange            |

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

| Field       | Type | Required | Description                               |
| ----------- | ---- | -------- | ----------------------------------------- |
| update_time | int  | no       | Refresh interval in seconds (default: 10) |

**Example:**

```bash
curl -N -X POST http://18.176.93.228/run-monitor \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"update_time": 10}' \
  -N
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
    "symbol": "NEW-USDT",
    "strategy": "slow_mm",
    "tier": "S",
    "mode": "normal",
    "hedge": "false",
    "auto_start": "true",
    "auto_restart": "true",
    "auto_config": "true",
    "model": "crossover_vol",
    "vol_param": "1.0",
    "trading_intensity_param": "1.0",
    "auto_start_ms": "true",
    "auto_restart_ms": "true",
    "auto_config_ms": "true"
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
    "symbol": "BTC-USDT",
    "strategy": "slow_mm"
  }'
```

**Valid values:**

- `market`: `spot`, `perp`
- `strategy`: `slow_mm`, `mid_mm`, `fast_mm`
- `tier`: `s`, `1`, `2`, `3` (spot only)
- `model`: `crossover_vol`, `kline_vol` (spot only)
- `mode`: `normal`, `stacker`

**Response:** `{"code": 200, "message": "success"}`

> If the symbol is not yet in market data, the response will include a note to call `/set_symbol_config` to register it first.

---

### 6. POST /setup_stacker_config

Configure stacker strategy (creates 1 feed + 4 gateway + 4 strategy files).

> **Ask admin for the correct `feed_host` and `gateway_host` values.**

**Payload:**

| Field              | Type   | Required | Description                                                        |
| ------------------ | ------ | -------- | ------------------------------------------------------------------ |
| exchanges          | string | yes      | `kucoin`, `binance`, `gate`, `bybit`                       |
| base_ccy           | string | yes      | Base currency (e.g.`RAVE`)                                       |
| quote_ccy          | string | yes      | Quote currency (e.g.`USDT`)                                      |
| market             | string | no       | `spot` (default) or `perp`                                     |
| feed_host          | string | yes      | Full feed host:port —**ask admin**                          |
| gateway_host       | string | yes      | Full gateway host:port —**ask admin**                       |
| tick_size          | number | yes      | Price tick size                                                    |
| quantity_step_size | number | yes      | Quantity step size                                                 |
| min_price          | number | yes      | Minimum price                                                      |
| max_price          | number | yes      | Maximum price                                                      |
| min_quantity       | number | yes      | Minimum order quantity                                             |
| max_quantity       | number | yes      | Maximum order quantity                                             |
| buy_stackers       | string | yes      | Proto-text stacker list:`[{price: X original_quantity: Y}, ...]` |
| sell_stackers      | string | yes      | Proto-text stacker list:`[{price: X original_quantity: Y}, ...]` |

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

**Response:**

```json
{
  "code": 200,
  "message": "success",
  "configs": {
    "feed": "configcpp/feed/kucoincpp_RAVE_USDT_stacker_feed.txtpb",
    "gateway": ["...1.txtpb", "...2.txtpb", "...3.txtpb", "...4.txtpb"],
    "strategy": ["...1.txtpb", "...2.txtpb", "...3.txtpb", "...4.txtpb"]
  }
}
```

---

### 7. POST /update_stacker_config

Update an existing stacker config. Only fields you provide are changed.

**Payload:**

| Field              | Type   | Required | Description                             |
| ------------------ | ------ | -------- | --------------------------------------- |
| exchanges          | string | yes      | Exchange name (to identify the config)  |
| base_ccy           | string | yes      | Base currency (to identify the config)  |
| quote_ccy          | string | yes      | Quote currency (to identify the config) |
| feed_host          | string | no       | New feed host:port                      |
| gateway_host       | string | no       | New gateway host:port                   |
| tick_size          | number | no       | New price tick size                     |
| quantity_step_size | number | no       | New quantity step size                  |
| min_price          | number | no       | New minimum price                       |
| max_price          | number | no       | New maximum price                       |
| min_quantity       | number | no       | New minimum order quantity              |
| max_quantity       | number | no       | New maximum order quantity              |
| buy_stackers       | array  | no       | Full new buy list                       |
| sell_stackers      | array  | no       | Full new sell list                      |

> At least one optional field must be provided. Must call `/setup_stacker_config` first.

**Example:**

```bash
curl -X POST http://18.176.93.228/update_stacker_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "exchanges": "kucoin",
    "base_ccy": "RAVE",
    "quote_ccy": "USDT",
    "max_price": 10.0,
    "sell_stackers": "[{price: 0.0610 original_quantity: 1000}]"
  }'
```

---

### 8. POST /start_volatility_model

Start a volatility model strategy (runs in background).

**Payload:**

| Field         | Type   | Required | Description                          |
| ------------- | ------ | -------- | ------------------------------------ |
| symbol        | string | yes      | `BASE-QUOTE` format                |
| market        | string | yes      | `spot` or `perp`                 |
| exchange      | string | yes      | Exchange name                        |
| exchange_data | string | yes      | Data source exchange                 |
| risk_tol      | string | yes      | `low`, `medium`, `high`        |
| strategy      | string | yes      | `slow_mm`, `mid_mm`, `fast_mm` |

**Example:**

```bash
curl -X POST http://18.176.93.228/start_volatility_model \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC-USDT", "market": "spot", "exchange": "kucoin", "exchange_data": "gate", "risk_tol": "low", "strategy": "slow_mm"}'
```

---

### 9. POST /set_symbol_config

Write a symbol's market config to Redis.

**Payload:**

| Field          | Type   | Required | Description                              |
| -------------- | ------ | -------- | ---------------------------------------- |
| base_currency  | string | yes      | Base currency (e.g.`ARCSOL`)           |
| quote_currency | string | yes      | Quote currency (e.g.`USDT`)            |
| market         | string | yes      | `spot` or `perp`                     |
| price_tick     | number | yes      | Minimum price increment                  |
| size_tick      | number | yes      | Minimum size increment                   |
| min_size       | number | yes      | Minimum order size                       |
| multiplier     | number | yes      | Contract multiplier (use `1` for spot) |
| contract_size  | number | yes      | Contract size (use `1` for spot)       |
| first_date     | number | yes      | Listing timestamp in milliseconds        |

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

**Response:** `{"code": 200, "message": "success", "symbol": "ARCSOL/USDT"}`

---

### 10. GET /check_volume_strat_inventory

Run inventory check. No body needed.

```bash
curl -X GET http://18.176.93.228/check_volume_strat_inventory \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2"
```

---

### 11. Volume Strategy Config

#### POST /setup_volume_config

**Payload:**

| Field           | Type   | Required | Description                   |
| --------------- | ------ | -------- | ----------------------------- |
| market          | string | yes      | `spot` or `perp`          |
| tier            | string | yes      | `a`, `b`, `c`, or `s` |
| base_ccy        | string | yes      | Base currency                 |
| quote_ccy       | string | yes      | Quote currency                |
| price_tick      | number | yes      | Price tick value              |
| price_tick_size | number | yes      | Price tick size               |
| qty_unit        | number | yes      | Quantity unit                 |

```bash
curl -X POST http://18.176.93.228/setup_volume_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"market": "spot", "tier": "a", "base_ccy": "BTC", "quote_ccy": "USDT", "price_tick": 0.1, "price_tick_size": 0.01, "qty_unit": 0.0001}'
```

#### POST /update_volume_config

**Payload:**

| Field           | Type   | Required | Description                   |
| --------------- | ------ | -------- | ----------------------------- |
| trade_symbol    | string | yes      | Format:`BASE-QUOTE`         |
| market          | string | yes      | `spot` or `perp`          |
| tier            | string | no       | If provided, reloads template |
| price_tick      | number | no       | Update price_tick             |
| price_tick_size | number | no       | Update price_tick_size        |
| qty_unit        | number | no       | Update qty_unit               |

```bash
curl -X POST http://18.176.93.228/update_volume_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"trade_symbol": "BTC-USDT", "market": "spot", "price_tick": 123.5}'
```

#### POST /remove_volume_strat_config

**Payload:**

| Field  | Type   | Required | Description           |
| ------ | ------ | -------- | --------------------- |
| symbol | string | yes      | Format:`BASE-QUOTE` |
| market | string | yes      | `spot` or `perp`  |

```bash
curl -X POST http://18.176.93.228/remove_volume_strat_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC-USDT", "market": "spot"}'
```

---

### 12. 1s Quoting Config

#### POST /setup_1s_quoting_config

**Payload:**

| Field     | Type   | Required | Description          |
| --------- | ------ | -------- | -------------------- |
| base_ccy  | string | yes      | Base currency        |
| quote_ccy | string | yes      | Quote currency       |
| market    | string | yes      | `spot` or `perp` |

```bash
curl -X POST http://18.176.93.228/setup_1s_quoting_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "BTC", "quote_ccy": "USDT", "market": "perp"}'
```

#### POST /update_1s_quoting_config

**Payload:**

| Field              | Type   | Required | Description               |
| ------------------ | ------ | -------- | ------------------------- |
| trade_symbol       | string | yes      | Format:`BASE-QUOTE`     |
| market             | string | yes      | `spot` or `perp`      |
| (any config field) | any    | no       | Any other field to update |

```bash
curl -X POST http://18.176.93.228/update_1s_quoting_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"trade_symbol": "BTC-USDT", "market": "perp", "max_position": 500}'
```

#### POST /remove_1s_quoting_config

**Payload:**

| Field  | Type   | Required | Description           |
| ------ | ------ | -------- | --------------------- |
| symbol | string | yes      | Format:`BASE-QUOTE` |
| market | string | yes      | `spot` or `perp`  |

```bash
curl -X POST http://18.176.93.228/remove_1s_quoting_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC-USDT", "market": "perp"}'
```

---

### 13. Arbitrage Strategy

#### POST /setup_arbitrage_strategy

**Payload:**

| Field             | Type   | Required | Description                                                  |
| ----------------- | ------ | -------- | ------------------------------------------------------------ |
| exchanges         | string | yes      | Comma-separated:`kucoin`, `gate`, `binance`, `bybit` |
| base_ccy          | string | yes      | Comma-separated, must match exchange count                   |
| quote             | string | yes      | Comma-separated, must match exchange count                   |
| market            | string | yes      | `spot` or `perp`                                         |
| taker_arb_min_bps | number | no       | Default: 5                                                   |
| maker_arb_min_bps | number | no       | Default: 20000                                               |
| max_order_amount  | number | no       | Default: 50                                                  |
| min_order_amount  | number | no       | Default: 20                                                  |

```bash
curl -X POST http://18.176.93.228/setup_arbitrage_strategy \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"exchanges": "kucoin,gate", "base_ccy": "BTC,BTC", "quote": "USDT,USDT", "market": "spot"}'
```

#### POST /update_arbitrage_strategy

**Payload:**

| Field             | Type   | Required | Description                          |
| ----------------- | ------ | -------- | ------------------------------------ |
| base_ccy          | string | yes      | Base currency of the existing config |
| market            | string | yes      | `spot` or `perp`                 |
| taker_arb_min_bps | number | no       |                                      |
| maker_arb_min_bps | number | no       |                                      |
| max_order_amount  | number | no       |                                      |
| min_order_amount  | number | no       |                                      |

```bash
curl -X POST http://18.176.93.228/update_arbitrage_strategy \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "BTC", "market": "spot", "taker_arb_min_bps": 120000}'
```

#### POST /remove_arbitrage_strategy

**Payload:**

| Field    | Type   | Required | Description                           |
| -------- | ------ | -------- | ------------------------------------- |
| base_ccy | string | yes      | Base currency of the config to remove |
| market   | string | yes      | `spot` or `perp`                  |

```bash
curl -X POST http://18.176.93.228/remove_arbitrage_strategy \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "BTC", "market": "spot"}'
```

---

### 14. POST /setup_new_listing_gateway

Generate a gateway config file for a new listing.

> **Ask admin for `host`, `feed_host`, and `account_id` values.**

**Payload:**

| Field        | Type   | Required | Description                                           |
| ------------ | ------ | -------- | ----------------------------------------------------- |
| gateway_name | string | yes      | Name for the generated file (no `.txtpb` extension) |
| market       | string | yes      | `spot` or `perp`                                  |
| host         | string | yes      | Gateway host:port —**ask admin**               |
| feed_host    | string | yes      | Feed host:port —**ask admin**                  |
| account_id   | string | yes      | Gateway account ID                                    |
| exchange     | string | no       | Default:`kucoin`                                    |

```bash
curl -X POST http://18.176.93.228/setup_new_listing_gateway \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "gateway_name": "emm_mirror_spot_gateway_custom_BASEUSDT",
    "market": "spot",
    "host": "<ask admin>",
    "feed_host": "<ask admin>",
    "account_id": "<ask admin>"
  }'
```

---

### 15. POST /setup_listing_strategy_gateway_feed

Set up feed subscription and strategy config files for a new listing.

> **Ask admin for `feed_host` and `gateway_host`.**

**Payload:**

| Field        | Type   | Required | Description          |
| ------------ | ------ | -------- | -------------------- |
| base_ccy     | string | yes      | Base currency        |
| quote_ccy    | string | yes      | Quote currency       |
| market       | string | yes      | `spot` or `perp` |
| gateway_host | string | yes      | **Ask admin**  |
| feed_host    | string | yes      | **Ask admin**  |

```bash
curl -X POST http://18.176.93.228/setup_listing_strategy_gateway_feed \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "BTC", "quote_ccy": "USDT", "market": "spot", "gateway_host": "<ask admin>", "feed_host": "<ask admin>"}'
```

---

### 16. Supervisor Config — New Listing

Register or remove programs in the supervisor config so processes can be managed via `supervisorctl`.

> **Ask admin for the correct `config_path` values.**

All setup endpoints return `409` if the program already exists. All remove endpoints return `404` if not found.

#### POST /setup_new_listing_gateway_supervisorctl

**Payload:**

| Field        | Type   | Required | Description                                     |
| ------------ | ------ | -------- | ----------------------------------------------- |
| program_name | string | yes      | Unique supervisor program name                  |
| config_path  | string | yes      | Full path to the gateway `.txtpb` config file |

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
  -d '{"program_name": "mirror_spot_listings_strat2_BTCUSDT", "config_path": "<ask admin>"}'
```

#### POST /remove_new_listing_strategy_supervisorctl

```bash
curl -X POST http://18.176.93.228/remove_new_listing_strategy_supervisorctl \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"program_name": "mirror_spot_listings_strat2_BTCUSDT"}'
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

| Field  | Type   | Required | Description                         |
| ------ | ------ | -------- | ----------------------------------- |
| method | string | yes      | `start`, `stop`, or `restart` |
| name   | string | yes      | Supervisorctl program name          |

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

**Required fields in `params`:**
`maker_exchange`, `taker_exchange`, `maker_market`, `taker_market`, `base_ccy`, `quote_ccy`, `maker_symbol`, `taker_symbol`, `target_inventory`, `max_inventory`, `rebalance_threshold`, `spread_bps`, `order_size`, `max_orders`, `cooldown_ms`, `maker_enabled`, `taker_enabled`, `withdraw`

**Conditional fields in `params`:**

- `perp_closing_mode` — required if either market is `perp`
- `maker_min_order_size` — required if `maker_enabled` is true
- `taker_min_order_size` — required if `taker_enabled` is true
- `withdraw_exchange`, `withdraw_token`, `withdraw_amount`, `withdraw_address`, `withdraw_network`, `withdraw_threshold`, `withdraw_interval_hours` — required if `withdraw` is true

```bash
curl -X POST http://18.176.93.228/setup_simple_arbitrage_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "my_arb_config",
    "params": { ... }
  }'
```

**Response:**

```json
{"code": 200, "message": "success", "configs": {"config": "path/to/config.json"}}
```

#### POST /update_simple_arbitrage_config

Update specific fields of an existing simple arbitrage config. Only the fields you provide in `params` are changed — everything else stays as-is. Returns `404` if the config doesn't exist.

```bash
curl -X POST http://18.176.93.228/update_simple_arbitrage_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "my_arb_config",
    "params": {"max_position_size_usdt": 5000, "hedge_price_bps": 3}
  }'
```

---

### 19. Simple Trader Config

#### POST /setup_simple_trader_config

Create a new simple trader config file. Returns `409` if it already exists — use `/update_simple_trader_config` instead.

**Required fields in `params`:**
`exchange`, `market`, `base_ccy`, `quote_ccy`, `symbol`, `order_size`, `max_position`, `spread_bps`

```bash
curl -X POST http://18.176.93.228/setup_simple_trader_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "my_trader_config",
    "params": { ... }
  }'
```

**Response:**

```json
{"code": 200, "message": "success", "configs": {"config": "path/to/config.json"}}
```

#### POST /update_simple_trader_config

Update specific fields of an existing simple trader config. Only the fields you provide in `params` are changed. Returns `404` if the config doesn't exist.

```bash
curl -X POST http://18.176.93.228/update_simple_trader_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "my_trader_config",
    "params": {"max_position": 1000}
  }'
```

---

## Common Workflows

### Workflow 1: Set up new listing

```bash
# 1. Register symbol config in Redis
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
  -d '{"market":"spot","tier":"a","base_ccy":"BTC","quote_ccy":"USDT","price_tick":0.1,"price_tick_size":0.01,"qty_unit":0.0001}'

# 2. Update params later
curl -X POST http://18.176.93.228/update_volume_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"trade_symbol":"BTC-USDT","market":"spot","price_tick":0.2}'

# 3. Remove when done
curl -X POST http://18.176.93.228/remove_volume_strat_config \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC-USDT","market":"spot"}'
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

---

## Troubleshooting

| Problem                       | Likely Cause                                | Solution                                         |
| ----------------------------- | ------------------------------------------- | ------------------------------------------------ |
| `401 unauthorized`          | Wrong/missing token                         | Check `Authorization: Bearer <TOKEN>` header   |
| `403 forbidden`             | Token not allowed on this endpoint          | Use the correct token for this endpoint type     |
| `404 check with admin`      | Endpoint URL typo                           | Verify endpoint name spelling                    |
| `400 Missing field: market` | Forgot to pass `market`                   | Add `"market": "spot"` or `"market": "perp"` |
| `404 Config not found`      | Trying to update/remove non-existent config | Run `setup_*` first                            |
| `409 already exists`        | Trying to create duplicate                  | Use `update_*` instead                         |
| `500 internal error`        | Server error                                | Send `request_id` to admin                     |
| `503 Service unreachable`   | Cannot reach the service                    | Tell admin                                       |
| `504 Service timed out`     | Exchange API slow                           | Retry, or tell admin if persists                 |

---

## Getting Help

When asking admin for help, always include:

1. The full `curl` command you ran (redact any sensitive values)
2. The complete JSON response (with `request_id`)
3. Approximate time of the request

Example:

> "I called `/setup_volume_config` at 14:30 with `request_id=abc123def456` and got `{"code": 500, "message": "internal error"}`. Can you check?"
