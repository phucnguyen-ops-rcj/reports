# Stacker Operations

Use this file for stacker setup, stacker config updates, and manual stacker run
notes. Do not execute commands unless explicitly asked.

Prefer Prefect UI deployments for repeated operations:

| Deployment | Use |
| --- | --- |
| `stacker-status` | Check accepted/rejected order output. |
| `launch-stacker` | Manually launch stacker for a symbol and level. |
| `setup-stacker-config` | Create stacker configs after hosts and stacker lists are known. |
| `update-stacker-config` | Update an existing stacker config using `updates_json`. |

These deployments run on `stacker-agent-pool`. All deployment output appears in
the Prefect flow run logs.
Leave `execution_mode=ssh` and `ssh_host=T1_newuser1` for these deployments.

`setup-stacker-config` defaults to the KAIO example: feed host
`0.0.0.0:41741`, gateway host `0.0.0.0:41799`, quantity step `0.1`, max price
`1.0`, buy stacker price `0.00194` quantity `5077.9708`, and sell stacker price
`0.95841` quantity `4780.6481`.

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
"feed_host":"0.0.0.0:41741","gateway_host":"0.0.0.0:41799"
```bash
curl -X POST http://18.176.93.228/setup_stacker_config \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "exchanges": "kucoin",
 "base_ccy": "SHARE",
 "quote_ccy": "USDT",
 "market": "spot",
 "feed_host": "0.0.0.0:41740",
 "gateway_host": "0.0.0.0:41799",
 "tick_size": 0.0001,
 "quantity_step_size": 0.01,
 "min_price": 0.0001,
 "max_price": 25.0,
 "min_quantity": 1.0,
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

## Manually Start Stacker

Prefect UI: use `launch-stacker`; most runs only change `symbol` and
`stacker_level`.

```bash
curl -X POST http://18.176.93.228/launch_stacker \
  -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"base_ccy": "METADAO", "quote_ccy": "USDT", "stacker_level": 1}'
```

## Check status

Prefect UI: use `stacker-status`; most runs only change `symbol`.

```bash
curl -X POST http://18.176.93.228/get_stacker_accepted_orders \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"symbol": "KAIO-USDT", "date": "20260504"}'
```
