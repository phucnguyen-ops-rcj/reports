# New Listing Curl Templates

Base endpoint: `http://18.176.93.228`

Auth header:

```bash
-H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}"
```

Use these templates by replacing placeholders. Output only the current step's command.

## Step 1 — Arbitrage Strategy Config

Required: `exchanges`, `base_ccy` repeated per exchange, `market`.

```bash
curl -X POST http://18.176.93.228/setup_arbitrage_strategy \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "exchanges": "kucoin,gate",
 "base_ccy": "BILL,BILL",
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
 "tier": "a",
 "base_ccy": "BILL",
 "quote_ccy": "USDT",
 "price_tick": 0.00001,
 "price_tick_size": 5,
 "qty_unit": 0.1
 }'
```

## Optional Step 2b — Stacker Config

Ask first. Required: `exchanges`, `base_ccy`, `market`, `feed_host`, `gateway_host`, tick/size/price/quantity fields, `buy_stackers`, `sell_stackers`.

```bash
curl -X POST http://18.176.93.228/setup_stacker_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "exchanges": "kucoin",
 "base_ccy": "BASE",
 "quote_ccy": "USDT",
 "market": "spot",
 "feed_host": "0.0.0.0:FEED_PORT",
 "gateway_host": "0.0.0.0:GATEWAY_PORT",
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

## Step 3 — New Listing Config (Redis)

Required: `exchange`, `market`, `symbol` as `BASE-USDT`.

```bash
curl -X POST http://18.176.93.228/setup_new_listing_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "exchange": "kucoin",
 "market": "spot",
 "symbol": "BILL-USDT",
 "strategy": "slow_mm",
 "tier": "A",
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
 "base_currency": "BILL",
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
Host 45718: BILL

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
 "base_ccy": "BILL",
 "quote_ccy": "USDT",
 "market": "spot",
 "gateway_host": "localhost:45718",
 "feed_host": "localhost:41743"
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
 "program_name": "mirror_spot_listings_strat2_BILLUSDT",
 "config_path": "configcpp/exchangemm_PROD/mirror/spot/strat2/emm_mirror_spot_strat2_BILLUSDT.txtpb"
 }'
```

After Phuc confirms Step 8 succeeded, update gateway memory.

## Step 9 — Start Volatility Model

Only if Phuc explicitly asks after token goes live.

```bash
curl -X POST http://18.176.93.228/start_volatility_model \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "symbol": "BASE-USDT",
 "market": "spot",
 "exchange": "kucoin",
 "exchange_data": "kucoin",
 "risk_tol": "low",
 "strategy": "slow_mm"
 }'
```

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
