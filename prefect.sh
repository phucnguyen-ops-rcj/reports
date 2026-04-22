#!/usr/bin/env bash
# start.sh — start Prefect server + deploy all flows + start worker
# Usage:
#   ./start.sh          # start everything
#   ./start.sh redeploy # redeploy flows then restart worker (use after code/env changes)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

PREFECT_API_URL="http://127.0.0.1:4200/api"
POOL="default-agent-pool"
SERVER_PID_FILE="$REPO_DIR/.prefect_server.pid"
WORKER_PID_FILE="$REPO_DIR/.prefect_worker.pid"

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

    # create pool if it doesn't exist, overwrite to suppress "already exists" warning
    uv run prefect work-pool create "$POOL" --type process --overwrite 2>/dev/null || true

    # deploy all flows from prefect.yaml, skip interactive prompts
    uv run prefect --no-prompt deploy --all

    echo "Flows deployed."
}

_start_worker() {
    echo "Starting worker..."
    nohup uv run prefect worker start --pool "$POOL" >  logs/prefect_worker.log 2>&1 &
    echo $! > "$WORKER_PID_FILE"
    echo "Worker started (PID $(cat "$WORKER_PID_FILE"))."
}

# ── redeploy mode: restart worker and re-deploy flows ──────────────────────────
if [[ "${1:-}" == "redeploy" ]]; then
    echo "=== Redeploying ==="
    # kill all orphaned workers (PID file only tracks the latest one)
    pkill -f "prefect worker start" 2>/dev/null || true
    _stop_pid_file "$WORKER_PID_FILE"
    sleep 2

    uv sync

    _deploy
    sleep 2

    _start_worker
    echo "=== Done. Worker restarted and flows redeployed. ==="
    exit 0
fi


# __ stop all prefect processes __
if [[ "${1:-}" == "stop" ]]; then
    _stop_pid_file "$WORKER_PID_FILE"
    _stop_pid_file "$SERVER_PID_FILE"
    pkill -f "prefect worker start" 2>/dev/null || true
    pkill -f "prefect server start" 2>/dev/null || true
    echo "=== All services stopped ==="
    exit 0
fi




# ── fresh start ────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "start" ]]; then
    echo "=== Starting Prefect ==="

    # stop any leftover processes
    _stop_pid_file "$WORKER_PID_FILE"
    _stop_pid_file "$SERVER_PID_FILE"

    uv sync

    # kill all prefect processes (server + workers)
    pkill -f "prefect worker start" 2>/dev/null || true
    pkill -f "prefect server start" 2>/dev/null || true
    sleep 2

    # start server
    nohup uv run prefect server start > logs/prefect_server.log 2>&1 &
    echo $! > "$SERVER_PID_FILE"

    _wait_for_server
    sleep 2

    _deploy
    sleep 2

    _start_worker

    echo ""
    echo "=== All services running ==="
    echo "  UI:     http://localhost:4200"
    echo "  Server: PID $(cat "$SERVER_PID_FILE")"
    echo "  Worker: PID $(cat "$WORKER_PID_FILE")"
    echo ""
    echo "To redeploy after code/env changes: ./start.sh redeploy"
    echo "To stop all services: ./start.sh stop"
    exit 0
fi
