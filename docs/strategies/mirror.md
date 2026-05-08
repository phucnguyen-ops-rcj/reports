`method` can be `start`, `stop`, or `restart`

Prefer Prefect UI deployment `mirror-control`, which runs on the `strategies`
work pool.

Most runs change:

- `symbol`
- `component`: `gateway`, `feed`, or `strategy`
- `method`: `start`, `stop`, or `restart`

The flow builds the standard process name automatically. Use `name_override`
when the supervisor process name is nonstandard. Output appears in the Prefect
flow run logs. Default execution mode and SSH host come from
`RCJ_OPS_EXECUTION_MODE` and `RCJ_OPS_SSH_HOST` in `.env`.

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
