Only after token goes live.

```bash
curl -X POST http://18.176.93.228/start_volatility_model \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{
 "symbol": "KAIO-USDT",
 "market": "spot",
 "exchange": "kucoin",
 "exchange_data": "kucoin",
 "risk_tol": "low",
 "strategy": "slow_mm"
 }'
```
