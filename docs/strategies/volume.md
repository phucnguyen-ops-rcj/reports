## Start Strategy

Prefect UI deployment:

- `volume-start-strategy`
- Runs on the `strategies` work pool.
- Most runs only change `symbol`.
- Default execution mode and SSH host come from `RCJ_OPS_EXECUTION_MODE` and
  `RCJ_OPS_SSH_HOST` in `.env`.
- Output appears in the Prefect flow run logs.

Equivalent curl:

```bash
curl -X POST http://18.176.93.228/start_volume_strategy \
  -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"base_currency": "KAIO", "quote_currency": "USDT"}'
```

## Check Status

Prefect UI deployment:

- `volume-fills`
- Runs on the `strategies` work pool.
- Most runs only change `symbol`; optionally set `date` as `YYYYMMDD`.
- Default execution mode and SSH host come from `RCJ_OPS_EXECUTION_MODE` and
  `RCJ_OPS_SSH_HOST` in `.env`.
- Output appears in the Prefect flow run logs.

Project command:

```bash
uv run strategy_fills KAIO
uv run strategy_fills KAIO-USDT
```

Flexible endpoint override:

```bash
uv run strategy_fills KAIO --endpoint /get_volume_strategy_fills
```

Equivalent curl:

```bash
curl -X POST http://18.176.93.228/get_volume_strategy_fills \
  -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d  '{"base_currency": "KAIO", "quote_currency": "USDT"}'
```
