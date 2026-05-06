`method` can be `start`, `stop`, or `restart`


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
