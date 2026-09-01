---
name: prefect-flows
description: Create, change, debug, or test Prefect flows in this repository's src/flows package, including matching prefect.yaml deployments. Use for report orchestration and strategy/ops flows; do not use for changes confined to the underlying report analysis scripts or API clients.
---

# Prefect Flows

Work from the repository root. Before editing, read `.codex/rules/prefect.md`, the
affected flow module, its focused tests, and any matching deployment in
`prefect.yaml`. Treat those files as the current source of truth if details in
this skill become stale.

## Choose the flow family

- Daily reports (`daily.py`, `market.py`, `net_pnl.py`, and
  `trading_volume.py`) follow load/fetch → analyze/format → save → notify.
  Keep file creation independent of Signal availability. Save all outputs before
  attempting notification, and keep notification failures non-fatal while still
  making the failure visible in logs or Prefect task state.
- `daily_flow` must invoke every child report even when one child fails. Capture
  child results with `return_state=True`; do not replace this with fail-fast
  sequential calls.
- Strategy and ops flows in `ops.py` are manual operational entry points. Keep
  flow parameters explicit and Prefect-serializable, preserve the configured SSH
  defaults, and isolate request/payload construction so it can be tested without
  a live service.

Use `@task` for retryable or separately observable work such as I/O and remote
calls. Keep simple deterministic orchestration in the flow unless a separate
task materially improves retries or Prefect visibility. Give flow and task names
stable, operator-readable labels.

## Preserve repository contracts

- Use settings from `src/settings.py`; prefer `get_settings()` inside new helper
  functions when that improves testability. Existing entry-point defaults may
  use `app_settings`.
- Import `SignalClient` directly from `src.clients.signal`. Do not let a send
  failure undo or prevent saved report artifacts; log caught send failures with
  `exc_info=True` when the failure is handled locally.
- Reuse analysis, formatting, persistence, and client functions from `src/scripts`,
  `src/utils`, and `src/clients`. Flows coordinate those functions rather than
  duplicating business logic.
- Preserve declared return shapes because parent flows and tests may consume
  paths or child states.
- Keep imports package-absolute (`src...`) and use module loggers. Do not call
  `logging.basicConfig()` in flow modules.

## Keep deployments aligned

When a deployable flow is added, removed, renamed, or gains parameters, inspect
and update `prefect.yaml` in the same change when necessary:

- Scheduled reports use the `daily-morning` pool.
- Mirror, stacker, volatility, and volume strategy deployments use `strategies`;
  their deployment names start with the corresponding strategy prefix.
- Do not recreate the retired `ops` pool or old manual deployments.
- Manual flows use no schedule. Put runtime environment overrides under
  `work_pool.job_variables.env`; flow arguments belong under `parameters`.
- Verify that every deployment entrypoint resolves to the actual module and flow
  function.

Editing a flow does not authorize deployment. Deploy only when the user asks,
and deploy the complete manifest with:

```bash
uv run prefect --no-prompt deploy --all
```

## Verify behavior

Test orchestration without live integrations. Call `.fn()` on Prefect-decorated
flows or tasks where direct execution is sufficient, monkeypatch dependencies at
the symbol imported by the flow module, and replace sleeps, Signal sends, SSH,
and API calls with fakes. Assert observable behavior: call order, payloads,
returned paths or states, non-fatal notification handling, and deployment-facing
defaults.

Run focused tests first, then broaden in proportion to the change:

```bash
uv run pytest tests/test_daily_flow.py
uv run pytest tests/test_net_pnl_flow.py
uv run pytest tests/test_ops_api.py
uv run pytest
```

Do not require a running Prefect server merely to validate flow logic. When the
task concerns server startup, workers, schedules, PostgreSQL, or deployment
diagnostics, follow the dedicated procedures in `.codex/rules/prefect.md`.
