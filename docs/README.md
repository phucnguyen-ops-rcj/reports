# Docs Index

This folder is the operational reference for repeated RCJ/report tasks. Keep
files small and task-specific so a future request can be answered by opening one
or two files.

## Files

| File | Use for |
| --- | --- |
| `api_reference.md` | Mini Service API conventions, responses, status codes, supported exchanges, and endpoint map. |
| `accounts.md` | Supported transfer/balance account aliases by exchange. |
| `arb_param_analysis.md` | Public-data analyzer for simple arbitrage order-size and fill-sleep parameters. |
| `ops_playbook.md` | Curl-only API command templates for balance, transfer, monitor, and health checks. |
| `prefect_ops.md` | Prefect UI deployments for new listing, volatility, stacker, mirror control, and diagnostics. |
| `new_listing.md` | Step-by-step new listing setup curl templates. |
| `gateway_inventory.md` | Memory for gateway host/feed host usage and when to allocate a new gateway. |
| `strategies/stacker.md` | Stacker setup, update, and manual run notes. |
| `strategies/mirror.md` | Mirror gateway/feed/strategy process control. |
| `strategies/volatility.md` | Volatility model start command. |
| `strategies/volume.md` | Volume strategy fill/status checks. |
| `strategy_configs.md` | Volume, 1s quoting, arbitrage, simple arbitrage, and simple trader config endpoints. |
| `diagnostics.md` | Log/search, channel availability, funding, positions, market profile, and fills endpoints. |
| `signal_setup.md` | Signal setup reference. |

## Maintenance Rules

- When a gateway host is assigned to a symbol, update `gateway_inventory.md`.
- When a new listing command changes, update `new_listing.md`.
- When a Prefect ops deployment changes, update `prefect_ops.md`.
- When an ops API template changes, update `ops_playbook.md`.
- When a Mini Service endpoint changes, update `api_reference.md` and the task-specific file.
- Keep secrets as environment variables such as `${RCJ_OPS_BEARER_TOKEN}`.
- Prefer concrete examples over generic placeholders when the safe default is
  known.
