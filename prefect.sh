#!/usr/bin/env bash
# prefect.sh — manage Prefect server, worker, and deployments
# Usage:
#   ./prefect.sh           # fresh start: kill old, start server + deploy + worker
#   ./prefect.sh stop      # gracefully stop server and worker
#   ./prefect.sh start     # restart stopped server and worker (no redeploy)
#   ./prefect.sh redeploy  # redeploy flows on running server, restart worker
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

PREFECT_API_URL="http://127.0.0.1:4200/api"
POOLS=(
    "default-agent-pool"
    "ops-agent-pool"
    "volatility-agent-pool"
    "volume-agent-pool"
    "stacker-agent-pool"
    "mirror-agent-pool"
)
SERVER_PID_FILE="$REPO_DIR/.prefect_server.pid"
LEGACY_WORKER_PID_FILE="$REPO_DIR/.prefect_worker.pid"
ENV_FILE="$REPO_DIR/.env"

_worker_pid_file() {
    echo "$REPO_DIR/.prefect_worker_$1.pid"
}

_load_prefect_database_env() {
    if [[ -z "${PREFECT_SERVER_DATABASE_CONNECTION_URL:-}" && -f "$ENV_FILE" ]]; then
        local line value
        line=$(grep -E '^PREFECT_SERVER_DATABASE_CONNECTION_URL=' "$ENV_FILE" | tail -n 1 || true)
        if [[ -n "$line" ]]; then
            value="${line#*=}"
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            export PREFECT_SERVER_DATABASE_CONNECTION_URL="$value"
        fi
    fi

    if [[ "${PREFECT_SERVER_DATABASE_CONNECTION_URL:-}" == postgresql* ]]; then
        echo "Prefect database: PostgreSQL connection configured."
    else
        echo "WARNING: PREFECT_SERVER_DATABASE_CONNECTION_URL is not set to PostgreSQL; Prefect may use SQLite." >&2
    fi
}

_stop_pid_file() {
    local pidfile="$1"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping PID $pid..."
            kill "$pid"
        fi
        rm -f "$pidfile"
    fi
}

_wait_for_server() {
    echo "Waiting for Prefect server..."
    for i in $(seq 1 20); do
        if curl -sf "$PREFECT_API_URL/health" > /dev/null 2>&1; then
            echo "Server is up."
            return 0
        fi
        sleep 1
    done
    echo "ERROR: Prefect server did not start in time." >&2
    exit 1
}

_deploy() {
    echo "Deploying flows..."
    uv run prefect config set PREFECT_API_URL="$PREFECT_API_URL" > /dev/null

    # create pools if they don't exist, overwrite to suppress "already exists" warnings
    for pool in "${POOLS[@]}"; do
        uv run prefect work-pool create "$pool" --type process --overwrite 2>/dev/null || true
    done

    # deploy all flows from prefect.yaml, skip interactive prompts
    uv run prefect --no-prompt deploy --all

    echo "Flows deployed."
}

_start_server() {
    echo "Starting server..."
    _load_prefect_database_env
    nohup uv run prefect server start >> logs/prefect_server.log 2>&1 &
    echo $! > "$SERVER_PID_FILE"
    echo "Server started (PID $(cat "$SERVER_PID_FILE"))."
}

_start_worker() {
    for pool in "${POOLS[@]}"; do
        local pidfile
        pidfile="$(_worker_pid_file "$pool")"
        echo "Starting worker for $pool..."
        nohup uv run prefect worker start --pool "$pool" >> "logs/prefect_worker_${pool}.log" 2>&1 &
        echo $! > "$pidfile"
        echo "Worker for $pool started (PID $(cat "$pidfile"))."
    done
}

# ── stop: gracefully stop server and worker ────────────────────────────────────
if [[ "${1:-}" == "stop" ]]; then
    echo "=== Stopping Prefect ==="
    _stop_pid_file "$LEGACY_WORKER_PID_FILE"
    for pool in "${POOLS[@]}"; do
        _stop_pid_file "$(_worker_pid_file "$pool")"
    done
    _stop_pid_file "$SERVER_PID_FILE"
    pkill -f "prefect worker start" 2>/dev/null || true
    pkill -f "prefect server start" 2>/dev/null || true
    echo "=== All services stopped ==="
    exit 0
fi

# ── start: restart stopped server and worker (no redeploy) ────────────────────
if [[ "${1:-}" == "start" ]]; then
    echo "=== Starting Prefect ==="
    _start_server
    _wait_for_server
    _start_worker
    echo ""
    echo "=== All services running ==="
    echo "  UI:     http://localhost:4200"
    echo "  Server: PID $(cat "$SERVER_PID_FILE")"
    for pool in "${POOLS[@]}"; do
        echo "  Worker $pool: PID $(cat "$(_worker_pid_file "$pool")")"
    done
    exit 0
fi

# ── redeploy: kill worker, redeploy on running server, restart worker ──────────
if [[ "${1:-}" == "redeploy" ]]; then
    echo "=== Redeploying ==="
    pkill -f "prefect worker start" 2>/dev/null || true
    sleep 2

    uv sync
    _deploy
    sleep 2

    _start_worker
    echo "=== Done. Worker restarted and flows redeployed. ==="
    exit 0
fi

# ── fresh start (no args): kill everything, start from scratch ─────────────────
echo "=== Fresh Start ==="

# stop gracefully first, then force-kill any orphans
_stop_pid_file "$LEGACY_WORKER_PID_FILE"
for pool in "${POOLS[@]}"; do
    _stop_pid_file "$(_worker_pid_file "$pool")"
done
_stop_pid_file "$SERVER_PID_FILE"
pkill -f "prefect worker start" 2>/dev/null || true
pkill -f "prefect server start" 2>/dev/null || true
sleep 2

uv sync

_start_server
_wait_for_server
sleep 2

_deploy
sleep 2

_start_worker

echo ""
echo "=== All services running ==="
echo "  UI:     http://localhost:4200"
echo "  Server: PID $(cat "$SERVER_PID_FILE")"
for pool in "${POOLS[@]}"; do
    echo "  Worker $pool: PID $(cat "$(_worker_pid_file "$pool")")"
done
echo ""
echo "Commands: ./prefect.sh stop | start | redeploy"
