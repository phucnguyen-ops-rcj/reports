Only after token goes live.

Prefect UI deployment:

- `start-volatility-model`
- Runs on `volatility-agent-pool`.
- Most runs only change `symbol`.
- Keep defaults unless the listing uses a different market, exchange, risk
  tolerance, or strategy.
- Leave `execution_mode=ssh` and `ssh_host=T1_newuser1`.
- Output appears in the Prefect flow run logs.

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
