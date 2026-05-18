# Prefect Ops UI

Use these manual deployments from the Prefect UI for RCJ strategy API work.
They run on the shared `strategies` work pool and are separate from daily
report jobs.

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

- `daily-morning` for scheduled report flows
- `strategies` for volatility, volume, stacker, and mirror flows

Strategy ops flows log the request payload, HTTP status, and cleaned response
body. Successful strategy actions also send a structured Signal group message
with an action title, the request payload, and the API response. Open the flow
run in the Prefect UI and check **Logs** for the same output you would normally
read in the terminal.

## Deployments

| Deployment | Work pool | Common use | Most-used parameters |
| --- | --- | --- | --- |
| `volatility-start-model` | `strategies` | Start volatility after a token is live. | `symbol`; usually keep `market`, `exchange`, `exchange_data`, `risk_tol`, and `strategy` defaults. |
| `volume-start-strategy` | `strategies` | Start the volume strategy for a symbol. | `symbol`. |
| `volume-fills` | `strategies` | Check volume strategy fill output. | `symbol`, optional `date`. |
| `stacker-status` | `strategies` | Check stacker accepted/rejected orders. | `symbol`, optional `date`. |
| `stacker-launch` | `strategies` | Manually launch stacker. | `symbol`, `stacker_level`. |
| `stacker-setup-config` | `strategies` | Create stacker configs. | `symbol`, `feed_host`, `gateway_host`, `buy_stackers`, `sell_stackers`. |
| `stacker-update-config` | `strategies` | Update existing stacker configs. | `symbol`, `updates_json`. |
| `mirror-control` | `strategies` | Start/stop/restart mirror gateway/feed/strategy processes. | `symbol`, `component`, `method`; use `name_override` for nonstandard process names. |

## Stacker Defaults

`stacker-setup-config` defaults to the KAIO example payload:

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
