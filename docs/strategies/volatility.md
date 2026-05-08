Only after token goes live.

Prefect UI deployment:

- `volatility-start-model`
- Runs on the `strategies` work pool.
- Most runs only change `symbol`.
- Keep defaults unless the listing uses a different market, exchange, risk
  tolerance, or strategy.
- Default execution mode and SSH host come from `RCJ_OPS_EXECUTION_MODE` and
  `RCJ_OPS_SSH_HOST` in `.env`.
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
