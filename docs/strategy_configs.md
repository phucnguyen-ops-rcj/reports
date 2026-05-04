# Strategy Config Endpoints

Use this file for config endpoints that are not part of the new-listing flow.
Do not execute commands unless explicitly asked.

Base endpoint: `http://18.176.93.228`

## Volume Strategy

### POST /setup_volume_config

Required: `market`, `tier`, `base_ccy`, `quote_ccy`, `price_tick`,
`price_tick_size`, `qty_unit`.

Valid `market`: `spot`, `perp`.

Valid `tier`: `a`, `b`, `c`, `s`.

```bash
curl -X POST http://18.176.93.228/setup_volume_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"market": "spot", "tier": "a", "base_ccy": "VSN", "quote_ccy": "USDT", "price_tick": 0.1, "price_tick_size": 0.01, "qty_unit": 0.0001}'
```

### POST /update_volume_config

Required: `trade_symbol`, `market`. Optional: `tier`, `price_tick`,
`price_tick_size`, `qty_unit`.

If `tier` is provided, the endpoint reloads the template.

```bash
curl -X POST http://18.176.93.228/update_volume_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"trade_symbol": "VSN-USDT", "market": "spot", "price_tick": 123.5}'
```

### POST /remove_volume_strat_config

Required: `symbol`, `market`.

```bash
curl -X POST http://18.176.93.228/remove_volume_strat_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"symbol": "VSN-USDT", "market": "spot"}'
```

## 1s Quoting

### POST /setup_1s_quoting_config

Required: `base_ccy`, `quote_ccy`, `market`.

```bash
curl -X POST http://18.176.93.228/setup_1s_quoting_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"base_ccy": "VSN", "quote_ccy": "USDT", "market": "spot"}'
```

### POST /update_1s_quoting_config

Required: `trade_symbol`, `market`. Any other config field may be included for
update.

```bash
curl -X POST http://18.176.93.228/update_1s_quoting_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"trade_symbol": "VSN-USDT", "market": "spot", "max_position": 500}'
```

### POST /remove_1s_quoting_config

Required: `symbol`, `market`.

```bash
curl -X POST http://18.176.93.228/remove_1s_quoting_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"symbol": "VSN-USDT", "market": "spot"}'
```

## Arbitrage Strategy

### POST /setup_arbitrage_strategy

Required: `exchanges`, `base_ccy`, `quote`, `market`.

Optional defaults:

- `taker_arb_min_bps`: `5`
- `maker_arb_min_bps`: `20000`
- `max_order_amount`: `50`
- `min_order_amount`: `20`

`exchanges`, `base_ccy`, and `quote` are comma-separated and must have matching
counts.

```bash
curl -X POST http://18.176.93.228/setup_arbitrage_strategy \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"exchanges": "kucoin,gate", "base_ccy": "VSN,VSN", "quote": "USDT,USDT", "market": "spot"}'
```

### POST /update_arbitrage_strategy

Required: `base_ccy`, `market`. Optional: `taker_arb_min_bps`,
`maker_arb_min_bps`, `max_order_amount`, `min_order_amount`.

```bash
curl -X POST http://18.176.93.228/update_arbitrage_strategy \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"base_ccy": "VSN", "market": "spot", "taker_arb_min_bps": 120000}'
```

### POST /remove_arbitrage_strategy

Required: `base_ccy`, `market`.

```bash
curl -X POST http://18.176.93.228/remove_arbitrage_strategy \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"base_ccy": "VSN", "market": "spot"}'
```

## Simple Arbitrage

### POST /setup_simple_arbitrage_config

Creates a new simple arbitrage config. Returns `409` if it already exists; use
`/update_simple_arbitrage_config` for existing configs.

Top-level required fields:

- `config_name`: unique alphanumeric/underscore config name
- `params`: object

Core `params` fields:

- `maker_exchange`, `taker_exchange`
- `maker_market`, `taker_market`: `spot` or `perp`
- `maker_side`, `taker_side`: `buy` or `sell`
- `base_currency`, `quote_currency`
- `maker_time_in_force`, `taker_time_in_force`
- `accumulation_mode`, `delta_threshold_usdt`, `max_settle_size_usdt`
- `maker_price_bps`, `hedge_price_bps`, `max_position_size_usdt`
- `update_portfolio_frequency_s`, `update_order_frequency_s`
- `adjust_closing_taker_usdt`, `maker_fill_sleep`, `taker_fill_sleep`
- `maker_min_order_size`, `taker_min_order_size`
- `withdraw`

Optional/conditional fields:

- `closing_mode`, `perp_closing_mode`, `auto_settlement`
- When `withdraw` is true: `maker_sub_to_main`, `taker_main_to_sub`,
  `transfer_from_exchange`, `transfer_to_exchange`, `transfer_ccy`,
  `transfer_wait_time_s`, `withdrawal_wait_time_s`,
  `deposit_amount_tolerance`, `chain`

```bash
curl -X POST http://18.176.93.228/setup_simple_arbitrage_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
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
   "maker_price_bps": 0.0,
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

### POST /update_simple_arbitrage_config

Updates only fields provided in `params`. Returns `404` if the config does not
exist.

Allowlisted config names only:

- `simple_arb_phuc_sp_pe_BNKC_FR_supervisor`
- `simple_arb_phuc_sp_pe_BYBKC_FR_supervisor`
- `simple_arb_phuc_sp_pe_GATKC_FR_supervisor`

```bash
curl -X POST http://18.176.93.228/update_simple_arbitrage_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "config_name": "simple_arb_phuc_sp_pe_BNKC_FR_supervisor",
 "params": {
   "base_currency": "KAT",
   "quote_currency": "USDT",
   "max_position_size_usdt": 200
 }
 }'
```

## Simple Trader

### POST /setup_simple_trader_config

Creates a simple trader config. Returns `409` if it already exists.

Top-level required fields:

- `config_name`
- `params`

Required `params`:

- `exchange`
- `market`: `spot` or `perp`
- `mode`: `usdt` or `token`
- `base_currency`, `quote_currency`
- `maker_enabled`, `taker_enabled`
- `side`
- `max_position`

Conditional `params`:

- `maker_min_order_size` when `maker_enabled` is true
- `taker_min_order_size` when `taker_enabled` is true

Common optional fields:

- `maker_price_bps`
- `maker_order_distance_bps`
- `taker_order_distance_bps`
- `maker_order_update_time_s`
- `taker_order_update_time_s`
- `information_update_time_s`
- `time_sleep_after_fill_s`

```bash
curl -X POST http://18.176.93.228/setup_simple_trader_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
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

### POST /update_simple_trader_config

Updates only fields provided in `params`. Returns `404` if the config does not
exist.

Allowlisted config names only:

- `simple_trade_phuc_pe_BN_FR_supervisor`
- `simple_trade_phuc_pe_KC_FR_supervisor`
- `simple_trade_phuc_sp_BN_FR_supervisor`
- `simple_trade_phuc_sp_GAT_FR_supervisor`
- `simple_trade_phuc_sp_KC_FR_supervisor`

```bash
curl -X POST http://18.176.93.228/update_simple_trader_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "config_name": "simple_trade_phuc_sp_KC_FR_supervisor",
 "params": {
   "base_currency": "ABCDEFG",
   "quote_currency": "USDT",
   "max_position": 100
 }
 }'
```
