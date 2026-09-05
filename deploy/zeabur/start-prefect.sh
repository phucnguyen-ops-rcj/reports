#!/usr/bin/env bash
set -Eeuo pipefail

server_host="${PREFECT_SERVER_HOST:-0.0.0.0}"
server_port="${PORT:-${PREFECT_SERVER_PORT:-4200}}"
health_url="http://127.0.0.1:${server_port}/api/health"

if [[ "${PREFECT_SERVER_DATABASE_CONNECTION_URL:-}" != postgresql* ]]; then
    echo "ERROR: PREFECT_SERVER_DATABASE_CONNECTION_URL must use PostgreSQL." >&2
    exit 1
fi

# All workers run beside the server in this container, so use its loopback API.
export PREFECT_API_URL="${PREFECT_INTERNAL_API_URL:-http://127.0.0.1:${server_port}/api}"

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

echo "Starting Prefect server on ${server_host}:${server_port}..."
uv run prefect server start --host "$server_host" --port "$server_port" &
server_pid=$!
pids+=("$server_pid")

server_ready=false
for _ in $(seq 1 60); do
    if curl --fail --silent "$health_url" >/dev/null; then
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
