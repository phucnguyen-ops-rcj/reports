# Gateway Inventory

Use this file as memory for gateway host usage. Before creating a new listing,
check the current symbol count for the target gateway.

## Allocation Rule

Create a new gateway when either condition is true:

- The current gateway has more than 10 symbols.
- The latest state says `needs_new_gateway: true`.

When creating a new gateway, save:

- `gateway_name`
- `market`
- `host`
- `feed_host`
- `account_id`
- assigned symbols
- `config_path` returned by `/setup_new_listing_gateway`

## Current Gateway State

| Market | Host | Feed Host | Account ID | Symbol Count | Symbols | State |
| --- | --- | --- | --- | ---: | --- | --- |
| spot | `0.0.0.0:45718` | `0.0.0.0:41700` | `ktfsmc15` | 1 | `BILL` | active |
| spot | `0.0.0.0:45718` | `0.0.0.0:41700` | `ktfsmc15` | 2 | `TAC` | active |
## Notes

- `Host 45718: BILL, TAC`
- Update `Symbol Count` whenever a symbol is added or removed.
- If `Symbol Count` becomes `11`, set state to `needs_new_gateway`.
