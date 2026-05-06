# New Listing Curl Templates

Base endpoint: `http://18.176.93.228`

Auth header:

```bash
-H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}"
```

Use these templates by replacing placeholders. Output only the current step's command.

For API response conventions, status codes, and troubleshooting, see `docs/api_reference.md`.

## Step 1 — Arbitrage Strategy Config

Required: `exchanges`, `base_ccy` repeated per exchange, `market`.

```bash
curl -X POST http://18.176.93.228/setup_arbitrage_strategy \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "exchanges": "kucoin,gate",
 "base_ccy": "TAC,TAC",
 "quote": "USDT,USDT",
 "market": "spot",
 "taker_arb_min_bps": 20,
 "maker_arb_min_bps": 20000,
 "max_order_amount": 50,
 "min_order_amount": 20
 }'
```

## Step 2 — Volume Config

Required: `market`, `tier`, `base_ccy`, `price_tick`, `price_tick_size`, `qty_unit`.

```bash
curl -X POST http://18.176.93.228/setup_volume_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "market": "spot",
 "tier": "b",
 "base_ccy": "TAC",
 "quote_ccy": "USDT",
 "price_tick": 0.00001,
 "price_tick_size": 5,
 "qty_unit": 0.1
 }'
```

## Optional Step 2b — Stacker Config

Use `docs/stacker.md` for setup, update, and manual stacker run notes.

## Step 3 — New Listing Config (Redis)

Required: `exchange`, `market`, `symbol` as `BASE-USDT`.

Valid values:

- `market`: `spot`, `perp`
- `strategy`: `slow_mm`, `mid_mm`, `fast_mm`
- `tier`: `s`, `1`, `2`, `3` for spot
- `model`: `crossover_vol`, `kline_vol` for spot
- `mode`: `normal`, `stacker`

```bash
curl -X POST http://18.176.93.228/setup_new_listing_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "exchange": "kucoin",
 "market": "spot",
 "symbol": "TAC-USDT",
 "strategy": "slow_mm",
 "tier": "B",
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

If the response says `symbol not found in market data`, ask: “Run Step 3b or go to Step 4?”

## Optional Step 3b — Set Symbol Config

Required: `base_currency`, `market`, `price_tick`, `size_tick`, `min_size`.

```bash
curl -X POST http://18.176.93.228/set_symbol_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "base_currency": "TAC",
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

## Step 4 — Create Gateway Config File

Before running, check `docs/gateway_inventory.md`.

Run only when current gateway has more than 10 symbols or state says `needs_new_gateway: true`. Required: `gateway_name`, `market`, `host` as `0.0.0.0:PORT`, `feed_host` as `0.0.0.0:PORT`, `account_id`.

```bash
curl -X POST http://18.176.93.228/setup_new_listing_gateway \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "gateway_name": "emm_mirror_spot_gateway_custom_BASEUSDT",
 "market": "spot",
 "host": "0.0.0.0:45718",
 "feed_host": "0.0.0.0:41700",
 "account_id": "ktfsmc15"
 }'
```

Save `config_path` for Step 5.
After success, update `docs/gateway_inventory.md` with the new host, feed host, account ID, symbol, and returned `config_path`.

## Step 5 — Register Gateway in Supervisorctl

Run only if Step 4 ran. Required: unique `program_name`, Step 4 `config_path` without `/home/ubuntu/`.

```bash
curl -X POST http://18.176.93.228/setup_new_listing_gateway_supervisorctl \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "program_name": "mirror_spot_gateway_custom_BASEUSDT",
 "config_path": "configcpp/exchangemm_PROD/mirror/spot/gateway/emm_mirror_spot_gateway_custom_BASEUSDT.txtpb"
 }'
```

## Step 6 — Create Feed + Strategy Config Files

Required: `base_ccy`, `market`, `gateway_host` as `localhost:SAME_GATEWAY_PORT`, `feed_host` as `localhost:FEED_PORT`.

```bash
curl -X POST http://18.176.93.228/setup_listing_strategy_gateway_feed \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "base_ccy": "TAC",
 "quote_ccy": "USDT",
 "market": "spot",
 "gateway_host": "localhost:45718",
 "feed_host": "localhost:41744"
 }'
```

Save `feed_config_path`, `strategy_config_path`, and `feed_action`.

## Step 7 — Register Feed in Supervisorctl

Run only if Step 6 says `feed_action: "created new feed file"`. Required: unique `program_name`, Step 6 `feed_config_path` without `/home/ubuntu/`.

```bash
curl -X POST http://18.176.93.228/setup_new_listing_feed_supervisorctl \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "program_name": "feed_spot_custom_kucoin_BASEUSDT",
 "config_path": "configcpp/exchangemm_PROD/feeds/spot/emm_spot_feed_custom_kucoin_BASEUSDT.txtpb"
 }'
```

## Step 8 — Register Strategy in Supervisorctl

Required: unique `program_name`, Step 6 `strategy_config_path` without `/home/ubuntu/`.

```bash
curl -X POST http://18.176.93.228/setup_new_listing_strategy_supervisorctl \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "program_name": "mirror_spot_listings_strat2_TACUSDT",
 "config_path": "configcpp/exchangemm_PROD/mirror/spot/strat2/emm_mirror_spot_strat2_TACUSDT.txtpb"
 }'
```


## Step 9 — Start Volatility Model

Only after token goes live.

```bash
curl -X POST http://18.176.93.228/start_volatility_model \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "symbol": "TAC-USDT",
 "market": "spot",
 "exchange": "kucoin",
 "exchange_data": "kucoin",
 "risk_tol": "low",
 "strategy": "slow_mm"
 }'
```

## Step 10 - Start Mirror Model

```bash
curl -X POST http://18.176.93.228/strategy_control \
  -H "Authorization: Bearer 3a71078c84c18f3310df39284341b4584e18d5284db906c8f5dbb721d5d9eed2" \
  -H "Content-Type: application/json" \
  -d '{"method": "start", "name": "mirror_spot_listings_strat2_KAIOUSDT"}'
```

`method` can be `start`, `stop`, or `restart`

## Process Control (only on explicit request)

Show only curl; never execute.

```bash
curl -X POST http://18.176.93.228/gateway_control \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"method": "start", "name": "mirror_spot_gateway_custom_BASEUSDT"}'
```

```bash
curl -X POST http://18.176.93.228/feed_control \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"method": "restart", "name": "feed_spot_custom_kucoin_BASEUSDT"}'
```

```bash
curl -X POST http://18.176.93.228/strategy_control \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"method": "start", "name": "mirror_spot_listings_strat2_BASEUSDT"}'
```
