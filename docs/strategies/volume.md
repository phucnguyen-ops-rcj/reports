## Start Strategy

Prefect UI deployment:

- `start-volume-strategy`
- Runs on `volume-agent-pool`.
- Most runs only change `symbol`.
- Leave `execution_mode=ssh` and `ssh_host=T1_newuser1`.
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

- `volume-strategy-fills`
- Runs on `volume-agent-pool`.
- Most runs only change `symbol`; optionally set `date` as `YYYYMMDD`.
- Leave `execution_mode=ssh` and `ssh_host=T1_newuser1`.
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
