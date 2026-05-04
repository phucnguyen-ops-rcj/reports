# Stacker Operations

Use this file for stacker setup, stacker config updates, and manual stacker run
notes. Do not execute commands unless explicitly asked.

Base endpoint: `http://18.176.93.228`

Auth header:

```bash
-H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}"
```

## Setup Stacker Config

Use as optional Step 2b in the new listing flow.

Required fields:

- `exchanges`
- `base_ccy`
- `quote_ccy`
- `market`
- `feed_host`
- `gateway_host`
- `tick_size`
- `quantity_step_size`
- `min_price`
- `max_price`
- `min_quantity`
- `max_quantity`
- `buy_stackers`
- `sell_stackers`

Ask for or look up the correct `feed_host` and `gateway_host` before filling
the command.

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

Response: plain text with file paths and all 4 strategy config previews, with
sensitive fields removed.

## Update Stacker Config

Use this endpoint only after `/setup_stacker_config` has already created the
stacker files.

Only fields provided in the request are changed. At least one optional update
field is required.

Required identity fields:

- `exchanges`
- `base_ccy`
- `quote_ccy`

Optional update fields:

- `feed_host`
- `gateway_host`
- `tick_size`
- `quantity_step_size`
- `min_price`
- `max_price`
- `min_quantity`
- `max_quantity`
- `buy_stackers`
- `sell_stackers`

Response behavior:

| Field changed | Feed shown | Gateway shown | Strategy shown |
| --- | --- | --- | --- |
| `max_price`, `tick_size`, size/quantity fields | yes | no | no |
| `feed_host` or `gateway_host` | yes | yes | all 4 |
| `buy_stackers` or `sell_stackers` only | no | no | all 4 |

`buy_stackers` and `sell_stackers` are full replacements. The new list replaces
all existing orders across all 4 strategy files.

```bash
curl -X POST http://18.176.93.228/update_stacker_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "exchanges": "kucoin",
 "base_ccy": "RAVE",
 "quote_ccy": "USDT",
 "max_price": 10.0,
 "sell_stackers": "[{price: 0.0610 original_quantity: 1000}]"
 }'
```

## Manual Stacker Run Notes

BILL stackers in T10:

At 3pm SG time:

```bash
LAUNCHER_ST ~/configcpp/strategy/kucoincpp_BILL_USDT_twkpi_st_1.txtpb ~/configcpp/gateway/kucoincpp_BILL_USDT_twkpi_st_1.txtpb ~/configcpp/feed/kucoincpp_BILL_USDT_stacker_feed.txtpb
```

At 3.10pm SG time:

```bash
LAUNCHER_ST ~/configcpp/strategy/kucoincpp_BILL_USDT_twkpi_st_2.txtpb ~/configcpp/gateway/kucoincpp_BILL_USDT_twkpi_st_2.txtpb
```

At 3.20pm SG time:

```bash
LAUNCHER_ST ~/configcpp/strategy/kucoincpp_BILL_USDT_twkpi_st_3.txtpb ~/configcpp/gateway/kucoincpp_BILL_USDT_twkpi_st_3.txtpb
```

At 3.30pm SG time:

```bash
LAUNCHER_ST ~/configcpp/strategy/kucoincpp_BILL_USDT_twkpi_st_4.txtpb ~/configcpp/gateway/kucoincpp_BILL_USDT_twkpi_st_4.txtpb
```
