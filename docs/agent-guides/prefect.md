# Prefect

## Database

- Prefect should run against the self-hosted PostgreSQL database, not SQLite.
- `.env` must define `PREFECT_SERVER_DATABASE_CONNECTION_URL`, for example:
  ```bash
  PREFECT_SERVER_DATABASE_CONNECTION_URL="postgresql+asyncpg://prefect:prefect@localhost:5432/prefect"
  ```
- `asyncpg` is required for the `postgresql+asyncpg://` driver and should stay in `pyproject.toml`.
- `prefect.sh` loads only `PREFECT_SERVER_DATABASE_CONNECTION_URL` from `.env` before `prefect server start`. Do not source the whole `.env` file from shell scripts because some project entries are app settings, not guaranteed shell syntax.
- To check whether Postgres is applied, start Prefect through `./prefect.sh` or `./prefect.sh start` and confirm the script prints `Prefect database: PostgreSQL connection configured.` before the server starts.
- If the script warns that the database URL is missing, Prefect may fall back to SQLite. Add the env var, ensure the Postgres container is running, then restart with `./prefect.sh stop` followed by `./prefect.sh start`.
- Local Postgres container command from the README:
  ```bash
  docker run -d \
    --name prefect-postgres \
    -e POSTGRES_USER=prefect \
    -e POSTGRES_PASSWORD=prefect \
    -e POSTGRES_DB=prefect \
    -p 5432:5432 \
    postgres:16
  ```

## Deployment

- All deployments are defined in `prefect.yaml` — never deploy individual flows via CLI.
- Deploy command: `uv run prefect --no-prompt deploy --all` (the `--no-prompt` flag must come before `deploy`).
- Work pool names: `daily-morning` for scheduled reports and `strategies` for
  mirror, stacker, volatility, and volume strategy flows. Strategy deployment
  names should start with their strategy prefix, for example `stacker-`,
  `volume-`, `volatility-`, or `mirror-`.
- The old `ops` work pool and its manual deployments were retired. Do not
  recreate them unless explicitly requested.
- Strategy RCJ ops API flows default to SSH execution through `T1_newuser1`
  because the Mini Service API is not reachable directly from local.
- To remove a stale deployment: `uv run prefect deployment delete 'Flow Name/deployment-name'`

## prefect.sh

- `./prefect.sh` — fresh start: stop old processes, run `uv sync`, start server, deploy, then start worker.
- `./prefect.sh stop` — gracefully stop server and worker, then kill orphan Prefect server/worker processes.
- `./prefect.sh start` — restart stopped server and worker without redeploying.
- `./prefect.sh redeploy` — run `uv sync`, redeploy flows on the running server, and restart the worker.
- `prefect.sh` should manage only the `daily-morning` and `strategies` pools.
- Prefect runtime logs live under `logs/prefect/`; runtime PID files live under
  `logs/pid/`. Root-level `.prefect_*.pid` files are legacy and should stay
  untracked.
- Killing all Prefect processes: `pkill -f "prefect server start" && pkill -f "prefect worker start"`

## zeabur.sh

- `./zeabur.sh` or `./zeabur.sh foreground` keeps the parent process in the
  foreground for the Zeabur service supervisor, while supervising the Prefect
  server and both workers.
- `./zeabur.sh start` and `./zeabur.sh restart` stop stale Prefect processes,
  then start the server and workers with `nohup` in the background without
  redeploying flows.
- `./zeabur.sh redeploy` performs a background restart and deploys every entry
  in `prefect.yaml` before starting the workers.
- `./zeabur.sh stop` stops PID-tracked processes and matching orphan Prefect
  processes. `./zeabur.sh status` reports server, worker, and API health.
- Zeabur background logs and PID files use the same `logs/prefect/` and
  `logs/pid/` directories as the local manager.

## SQLite fallback and lock errors

`sqlite3.OperationalError: database is locked` usually means Prefect is still using SQLite or multiple server processes are writing simultaneously. Prefer fixing the Postgres env var first, then ensure only one server is running. The fresh start path kills orphans with `pkill -f "prefect server start"` before launching.

## Schedule

- Defined in `prefect.yaml` under `schedules:` for the `daily-morning` deployment.
- The schedule currently uses cron `30 9 * * *` with timezone `Asia/Singapore`.
- The Prefect UI displays schedules in local machine timezone; compare using explicit timezones when debugging schedule timing.
- Deployments with no `schedules:` entry (or `schedules: []`) are manual-trigger only.

## Job Variables vs Parameters

- **Parameters** — passed to the flow function as arguments.
- **Job Variables** — control the worker process environment. Env var overrides must be nested under `env`:
  ```json
  { "env": { "MY_VAR": "value" } }
  ```
  Top-level keys map to worker infrastructure options (`working_dir`, `pip_packages`), not env vars.

## Known warnings (harmless, from Prefect internals)

- `WheneverDeprecationWarning: py_datetime() is deprecated` — from `prefect/types/_datetime.py` and `prefect/server/schemas/schedules.py`. Not your code, no fix needed.
