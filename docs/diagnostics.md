# Diagnostics Endpoints

Use these curl templates for read-only diagnostics. Do not execute unless asked.

Base endpoint: `http://18.176.93.228`

## Stacker Accepted Orders

Search stacker strategy logs for accepted and rejected order responses.
Rejected orders are deduplicated by `order_id`.

Required: `symbol`. Optional: `date` as `YYYYMMDD`, default today.

```bash
curl -X POST http://18.176.93.228/get_stacker_accepted_orders \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"symbol": "BILL-USDT", "date": "20260504"}'
```

## Token Channel Availability

Check deposit and withdrawal status for a token across supported exchanges.

Required: `token`.

```bash
curl -X POST http://18.176.93.228/get_token_chan_availability \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"token": "KAT"}'
```

## Funding Rate Snapshot

Get a funding snapshot with 24-hour lookback and exchange history.

Required: `token`.

```bash
curl -X POST http://18.176.93.228/get_funding_rate_snapshot \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"token": "KAT"}'
```

## Position Information

Fetch plain text position/PnL information.

Required: `token`, `db`.

```bash
curl -X POST http://18.176.93.228/fetch_position_information \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"token": "KAT", "db": 53}'
```

## Token Market Profile

Get pacing envelope analysis, estimated daily capacity, completion time, and
per-venue sizing for a token and program size.

Required: `token`, `order_size_token`.

```bash
curl -X POST http://18.176.93.228/get_token_market_profile \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"token": "KAT", "order_size_token": 100000}'
```

## Volume Strategy Fills

Search volume strategy logs for `UPD_FILL` events.

Required: `base_currency`, `quote_currency`. Optional: `date` as `YYYYMMDD`,
default today.

```bash
curl -X POST http://18.176.93.228/get_volume_strategy_fills \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"base_currency": "ASSET", "quote_currency": "USDT", "date": "20260430"}'
```
