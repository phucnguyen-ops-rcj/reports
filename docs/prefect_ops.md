# Prefect Ops UI

Use these manual deployments from the Prefect UI for RCJ ops API work. They run
on strategy-specific work pools and are separate from daily report jobs.

Configure the default Mini Service API route in `.env`:

- `RCJ_OPS_EXECUTION_MODE`: `ssh` or `local`
- `RCJ_OPS_SSH_HOST`: SSH host used when execution mode is `ssh`
- `RCJ_OPS_BASE_ENDPOINT`: Mini Service API base URL

When `RCJ_OPS_EXECUTION_MODE=ssh`, the Prefect worker SSHes to
`RCJ_OPS_SSH_HOST`, performs the API request from there, and captures the HTTP
status/body back into the Prefect run logs. Use `local` only from a machine that
can reach the API directly.

Start or redeploy Prefect with:

```bash
./prefect.sh
./prefect.sh redeploy
```

The script creates these work pools and starts workers for:

- `default-agent-pool` for scheduled report flows
- `ops-playbook-agent-pool` for balance, transfer, monitor, and health checks
- `ops-agent-pool` for generic/new-listing ops flows
- `volatility-agent-pool` for volatility model flows
- `volume-agent-pool` for volume strategy flows
- `stacker-agent-pool` for stacker flows
- `mirror-agent-pool` for mirror process control flows

All ops flows log the request payload, HTTP status, and raw response body. Open
the flow run in the Prefect UI and check **Logs** for the same output you would
normally read in the terminal.

## Deployments

| Deployment | Work pool | Common use | Most-used parameters |
| --- | --- | --- | --- |
| `ops-health` | `ops-playbook-agent-pool` | Check Mini Service API health. | Usually none. |
| `ops-get-balance` | `ops-playbook-agent-pool` | Get token balance for an exchange/account. | `exchange`, `account`, `token`; `market` for futures. |
| `ops-run-transfer` | `ops-playbook-agent-pool` | Run transfer/withdrawal operations. | `mode`, `token`, `from_exchange`, `amount`, plus mode-specific fields. |
| `ops-run-monitor` | `ops-playbook-agent-pool` | Run a bounded monitor sample. | `update_time`, `timeout_seconds`. |
| `new-listing` | `ops-agent-pool` | Run `src/config/new_listing/<symbol>.json` setup. | `symbol`, `dry_run`; use `config_path` only for custom files. |
| `start-volatility-model` | `volatility-agent-pool` | Start volatility after a token is live. | `symbol`; usually keep `market`, `exchange`, `exchange_data`, `risk_tol`, and `strategy` defaults. |
| `start-volume-strategy` | `volume-agent-pool` | Start the volume strategy for a symbol. | `symbol`. |
| `volume-strategy-fills` | `volume-agent-pool` | Check volume strategy fill output. | `symbol`, optional `date`. |
| `stacker-status` | `stacker-agent-pool` | Check stacker accepted/rejected orders. | `symbol`, optional `date`. |
| `launch-stacker` | `stacker-agent-pool` | Manually launch stacker. | `symbol`, `stacker_level`. |
| `setup-stacker-config` | `stacker-agent-pool` | Create stacker configs. | `symbol`, `feed_host`, `gateway_host`, `buy_stackers`, `sell_stackers`. |
| `update-stacker-config` | `stacker-agent-pool` | Update existing stacker configs. | `symbol`, `updates_json`. |
| `mirror-control` | `mirror-agent-pool` | Start/stop/restart mirror gateway/feed/strategy processes. | `symbol`, `component`, `method`; use `name_override` for nonstandard process names. |
| `ops-api-request` | `ops-agent-pool` | Escape hatch for another POST endpoint. | `endpoint`, `payload_json`. |

## Stacker Defaults

`setup-stacker-config` defaults to the KAIO example payload:

- `symbol`: `KAIO`
- `feed_host`: `0.0.0.0:41741`
- `gateway_host`: `0.0.0.0:41799`
- `quantity_step_size`: `0.1`
- `max_price`: `1.0`
- `buy_stackers`: price `0.00194`, quantity `5077.9708`
- `sell_stackers`: price `0.95841`, quantity `4780.6481`

## Parameter Patterns

Most symbol fields accept either `BASE` or `BASE-USDT`; flows normalize to
`BASE-USDT` or extract `BASE` depending on the endpoint.

Set `RCJ_OPS_SSH_HOST` in `.env` when the ops API route moves to another
reachable machine.

Use JSON object strings for flexible fields:

```json
{"max_price": 10.0, "sell_stackers": "[{price: 0.0610 original_quantity: 1000}]"}
```

For mirror process control, the default process names are generated from
`symbol`, `component`, `exchange`, and `market`:

- gateway: `mirror_spot_gateway_custom_BASEUSDT`
- feed: `feed_spot_custom_kucoin_BASEUSDT`
- strategy: `mirror_spot_listings_strat2_BASEUSDT`

Set `name_override` when the deployed process name does not match the default.
