#!/usr/bin/env bash
# Start the self-hosted Prefect server and workers inside a Zeabur service.
set -Eeuo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

env_file="${ENV_FILE:-${repo_dir}/.env}"

load_env_value() {
    local name="$1"
    local line value

    if [[ -n "${!name:-}" || ! -f "$env_file" ]]; then
        return
    fi

    line="$(grep -E "^${name}=" "$env_file" | tail -n 1 || true)"
    if [[ -z "$line" ]]; then
        return
    fi

    value="${line#*=}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf -v "$name" '%s' "$value"
    export "$name"
}

for setting_name in \
    PREFECT_SERVER_DATABASE_CONNECTION_URL \
    POSTGRES_CONNECTION_STRING \
    PREFECT_SERVER_API_AUTH_STRING \
    PREFECT_API_AUTH_STRING \
    PREFECT_PUBLIC_URL; do
    load_env_value "$setting_name"
done

server_host="${PREFECT_SERVER_HOST:-0.0.0.0}"
server_port="${PORT:-${PREFECT_SERVER_PORT:-4200}}"
internal_api_url="${PREFECT_INTERNAL_API_URL:-http://127.0.0.1:${server_port}/api}"
public_url="${PREFECT_PUBLIC_URL:-${ZEABUR_WEB_URL:-}}"
database_url="${PREFECT_SERVER_DATABASE_CONNECTION_URL:-${POSTGRES_CONNECTION_STRING:-}}"

case "$database_url" in
    postgresql+asyncpg://*) ;;
    postgresql://*) database_url="postgresql+asyncpg://${database_url#postgresql://}" ;;
    postgres://*) database_url="postgresql+asyncpg://${database_url#postgres://}" ;;
    *)
        echo "ERROR: Set PREFECT_SERVER_DATABASE_CONNECTION_URL or expose POSTGRES_CONNECTION_STRING from Zeabur PostgreSQL." >&2
        exit 1
        ;;
esac

if [[ -z "${PREFECT_SERVER_API_AUTH_STRING:-}" ]]; then
    echo "ERROR: Set PREFECT_SERVER_API_AUTH_STRING to username:password in Zeabur." >&2
    exit 1
fi

export PREFECT_SERVER_DATABASE_CONNECTION_URL="$database_url"
export PREFECT_API_URL="$internal_api_url"
export PREFECT_API_AUTH_STRING="${PREFECT_API_AUTH_STRING:-${PREFECT_SERVER_API_AUTH_STRING}}"

if [[ -n "$public_url" ]]; then
    public_url="${public_url%/}"
    export PREFECT_UI_URL="$public_url"
    export PREFECT_SERVER_UI_API_URL="${public_url}/api"
    echo "Prefect UI: $public_url"
else
    echo "WARNING: Bind a Zeabur domain or set PREFECT_PUBLIC_URL, then redeploy so the UI can reach the API." >&2
fi

pids=()

shutdown() {
    local pid
    for pid in "${pids[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
}

trap shutdown EXIT
trap 'exit 143' TERM INT

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is not installed. Install it before running this script." >&2
    echo "See https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

echo "Installing locked project dependencies..."
uv sync --frozen --no-dev

echo "Starting Prefect server on ${server_host}:${server_port}..."
uv run prefect server start --host "$server_host" --port "$server_port" &
server_pid=$!
pids+=("$server_pid")

server_ready=false
for _ in $(seq 1 60); do
    if curl --fail --silent \
        --user "$PREFECT_API_AUTH_STRING" \
        "${internal_api_url}/health" >/dev/null; then
        server_ready=true
        break
    fi
    if ! kill -0 "$server_pid" 2>/dev/null; then
        wait "$server_pid"
        exit $?
    fi
    sleep 2
done

if [[ "$server_ready" != true ]]; then
    echo "ERROR: Prefect server did not become healthy within 120 seconds." >&2
    exit 1
fi

echo "Creating Prefect work pools..."
uv run prefect work-pool create daily-morning --type process --overwrite
uv run prefect work-pool create strategies --type process --overwrite

echo "Deploying all flows from prefect.yaml..."
uv run prefect --no-prompt deploy --all

echo "Starting Prefect workers..."
uv run prefect worker start --pool daily-morning &
pids+=("$!")
uv run prefect worker start --pool strategies &
pids+=("$!")

echo "Prefect server and workers are running."
set +e
wait -n "${pids[@]}"
exit_code=$?
set -e

echo "ERROR: A Prefect service exited with status ${exit_code}." >&2
if [[ "$exit_code" -eq 0 ]]; then
    exit_code=1
fi
exit "$exit_code"
