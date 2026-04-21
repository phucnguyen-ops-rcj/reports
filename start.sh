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

    # create pool if it doesn't exist
    uv run prefect work-pool create "$POOL" --type process 2>/dev/null || true

    uv run prefect deploy src/flows/daily.py:daily_flow \
        --name "daily-morning" --cron "20 4 * * *" \
        --pool "$POOL" --no-upload

    uv run prefect deploy src/flows/market.py:market_flow \
        --name "market-manual" --pool "$POOL" --no-upload

    uv run prefect deploy src/flows/net_pnl.py:net_pnl_flow \
        --name "net-pnl-manual" --pool "$POOL" --no-upload

    uv run prefect deploy src/flows/trading_volume.py:trading_volume_flow \
        --name "trading-volume-manual" --pool "$POOL" --no-upload

    echo "Flows deployed."
}

_start_worker() {
    echo "Starting worker..."
    uv run prefect worker start --pool "$POOL" &
    echo $! > "$WORKER_PID_FILE"
    echo "Worker started (PID $(cat "$WORKER_PID_FILE"))."
}

# ── redeploy mode: restart worker and re-deploy flows ──────────────────────────
if [[ "${1:-}" == "redeploy" ]]; then
    echo "=== Redeploying ==="
    _stop_pid_file "$WORKER_PID_FILE"
    uv sync
    _deploy
    _start_worker
    echo "=== Done. Worker restarted and flows redeployed. ==="
    exit 0
fi

# ── fresh start ────────────────────────────────────────────────────────────────
echo "=== Starting Prefect ==="

# stop any leftover processes
_stop_pid_file "$SERVER_PID_FILE"
_stop_pid_file "$WORKER_PID_FILE"

uv sync

# start server in background
uv run prefect server start &
echo $! > "$SERVER_PID_FILE"
echo "Server started (PID $(cat "$SERVER_PID_FILE")). UI: http://localhost:4200"

_wait_for_server
_deploy
_start_worker

echo ""
echo "=== All services running ==="
echo "  UI:     http://localhost:4200"
echo "  Server: PID $(cat "$SERVER_PID_FILE")"
echo "  Worker: PID $(cat "$WORKER_PID_FILE")"
echo ""
echo "To redeploy after code/env changes: ./start.sh redeploy"
