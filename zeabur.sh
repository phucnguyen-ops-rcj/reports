#!/usr/bin/env bash
# Manage the self-hosted Prefect server and workers on Zeabur.
# Usage:
#   ./zeabur.sh              # foreground mode for the Zeabur service supervisor
#   ./zeabur.sh start        # restart server/workers in the background
#   ./zeabur.sh restart      # alias for start
#   ./zeabur.sh redeploy     # background restart and deploy all flows
#   ./zeabur.sh stop         # stop server/workers and remove stale PID files
#   ./zeabur.sh status       # show PID and API health status
set -Eeuo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"
export REPORTS_REPO_DIR="$repo_dir"

env_file="${ENV_FILE:-${repo_dir}/.env}"
log_dir="${PREFECT_LOG_DIR:-${repo_dir}/logs/prefect}"
pid_dir="${PREFECT_PID_DIR:-${repo_dir}/logs/pid}"
server_pid_file="${pid_dir}/prefect_server.pid"
pools=("daily-morning" "strategies")

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

worker_pid_file() {
    echo "${pid_dir}/prefect_worker_$1.pid"
}

ensure_runtime_dirs() {
    mkdir -p "$log_dir" "$pid_dir"
}

ensure_uv() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "ERROR: uv is not installed. See https://docs.astral.sh/uv/getting-started/installation/." >&2
        exit 1
    fi
}

prepare_runtime() {
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
        echo "WARNING: Bind a Zeabur domain or set PREFECT_PUBLIC_URL so the UI can reach the API." >&2
    fi
}

pid_is_running() {
    local pid_file="$1"
    local pid

    [[ -f "$pid_file" ]] || return 1
    pid="$(cat "$pid_file")"
    [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

stop_pid_file() {
    local pid_file="$1"
    local pid

    if ! pid_is_running "$pid_file"; then
        rm -f "$pid_file"
        return
    fi

    pid="$(cat "$pid_file")"
    echo "Stopping PID $pid..."
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 50); do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$pid_file"
            return
        fi
        sleep 0.2
    done

    echo "PID $pid did not stop gracefully; forcing shutdown." >&2
    kill -KILL "$pid" 2>/dev/null || true
    rm -f "$pid_file"
}

kill_orphan_workers() {
    local pool
    for pool in "${pools[@]}"; do
        pkill -f "prefect worker start --pool ${pool}" 2>/dev/null || true
    done
}

kill_orphan_server() {
    pkill -f "prefect server start" 2>/dev/null || true
}

stop_workers() {
    local pool
    for pool in "${pools[@]}"; do
        stop_pid_file "$(worker_pid_file "$pool")"
    done
    kill_orphan_workers
}

stop_all() {
    ensure_runtime_dirs
    stop_workers
    stop_pid_file "$server_pid_file"
    kill_orphan_server
}

api_is_healthy() {
    local auth_string="${PREFECT_API_AUTH_STRING:-${PREFECT_SERVER_API_AUTH_STRING:-}}"
    local curl_args=(--fail --silent)

    if [[ -n "$auth_string" ]]; then
        curl_args+=(--user "$auth_string")
    fi
    curl "${curl_args[@]}" "${internal_api_url}/health" >/dev/null
}

wait_for_server() {
    echo "Waiting for Prefect server..."
    for _ in $(seq 1 60); do
        if api_is_healthy; then
            echo "Prefect server is healthy."
            return 0
        fi
        if ! pid_is_running "$server_pid_file"; then
            echo "ERROR: Prefect server exited during startup." >&2
            if [[ -f "${log_dir}/server.log" ]]; then
                tail -n 40 "${log_dir}/server.log" >&2
            fi
            return 1
        fi
        sleep 2
    done
    echo "ERROR: Prefect server did not become healthy within 120 seconds." >&2
    return 1
}

sync_dependencies() {
    echo "Installing locked project dependencies..."
    uv sync --frozen --no-dev
}

configure_profile() {
    # The server preflight check reads the active profile, not only the environment.
    uv run prefect config set PREFECT_API_URL="$internal_api_url" >/dev/null
}

ensure_work_pools() {
    local pool
    echo "Creating Prefect work pools..."
    for pool in "${pools[@]}"; do
        uv run prefect work-pool create "$pool" --type process --overwrite
    done
}

deploy_all() {
    ensure_work_pools
    echo "Deploying all flows from prefect.yaml..."
    uv run prefect --no-prompt deploy --all
}

start_server_background() {
    ensure_runtime_dirs
    echo "Starting Prefect server in the background on ${server_host}:${server_port}..."
    nohup uv run prefect server start --host "$server_host" --port "$server_port" \
        </dev/null >>"${log_dir}/server.log" 2>&1 &
    echo "$!" > "$server_pid_file"
}

start_workers_background() {
    local pool pid_file
    for pool in "${pools[@]}"; do
        pid_file="$(worker_pid_file "$pool")"
        echo "Starting background worker for ${pool}..."
        nohup uv run prefect worker start --pool "$pool" \
            </dev/null >>"${log_dir}/worker_${pool}.log" 2>&1 &
        echo "$!" > "$pid_file"
    done
}

print_status() {
    local pool pid_file
    echo "Prefect UI: ${public_url:-not configured}"
    if pid_is_running "$server_pid_file"; then
        echo "Server: running (PID $(cat "$server_pid_file"))"
    else
        echo "Server: stopped"
    fi
    for pool in "${pools[@]}"; do
        pid_file="$(worker_pid_file "$pool")"
        if pid_is_running "$pid_file"; then
            echo "Worker ${pool}: running (PID $(cat "$pid_file"))"
        else
            echo "Worker ${pool}: stopped"
        fi
    done
    if api_is_healthy; then
        echo "API: healthy"
    else
        echo "API: unavailable"
    fi
}

start_background() {
    local should_deploy="${1:-false}"

    ensure_uv
    prepare_runtime
    stop_all
    sync_dependencies
    configure_profile
    start_server_background
    if ! wait_for_server; then
        stop_all
        return 1
    fi
    if [[ "$should_deploy" == "true" ]]; then
        deploy_all
    else
        ensure_work_pools
    fi
    start_workers_background
    print_status
    echo "Logs: ${log_dir}"
}

foreground_cleanup() {
    trap - EXIT TERM INT
    stop_all
}

run_foreground() {
    local pool exit_code
    local -a child_pids=()

    ensure_uv
    prepare_runtime
    stop_all
    sync_dependencies
    configure_profile

    trap foreground_cleanup EXIT
    trap 'foreground_cleanup; exit 143' TERM INT

    echo "Starting Prefect server on ${server_host}:${server_port}..."
    uv run prefect server start --host "$server_host" --port "$server_port" &
    echo "$!" > "$server_pid_file"
    child_pids+=("$!")
    wait_for_server
    deploy_all

    echo "Starting Prefect workers..."
    for pool in "${pools[@]}"; do
        uv run prefect worker start --pool "$pool" &
        echo "$!" > "$(worker_pid_file "$pool")"
        child_pids+=("$!")
    done

    echo "Prefect server and workers are running."
    set +e
    wait -n "${child_pids[@]}"
    exit_code=$?
    set -e
    echo "ERROR: A Prefect service exited with status ${exit_code}." >&2
    if [[ "$exit_code" -eq 0 ]]; then
        exit_code=1
    fi
    return "$exit_code"
}

case "${1:-foreground}" in
    foreground|run)
        run_foreground
        ;;
    start|restart)
        start_background false
        ;;
    redeploy)
        start_background true
        ;;
    stop)
        echo "Stopping Prefect server and workers..."
        stop_all
        echo "Prefect services stopped."
        ;;
    status)
        ensure_runtime_dirs
        print_status
        ;;
    *)
        echo "Usage: $0 [foreground|start|restart|redeploy|stop|status]" >&2
        exit 2
        ;;
esac
