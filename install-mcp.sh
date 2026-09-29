#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CACHE_DIR="$ROOT_DIR/.cache/decisionlab-mcp"
PID_FILE="$CACHE_DIR/backend.pid"
LOG_FILE="$CACHE_DIR/backend.log"
ENV_FILE="$CACHE_DIR/env.sh"

usage() {
  cat <<'EOF'
Usage:
  ./install-mcp.sh [DATASET_ROOT [DATASET_FOLDER]]
  ./install-mcp.sh --stop

Installs dependencies, runs the offline test suites, starts an isolated
DecisionLab backend, verifies all six MCP tools, and prepares one benchmark.
The bundled sample dataset is used when no dataset root is supplied.

Environment overrides:
  DECISIONLAB_MCP_PORT       Backend port (default: 8879)
  DECISIONLAB_MCP_DATA_ROOT Backend evidence directory

This installer does not make live Jev or Laya calls. Live execution still
requires an explicit advance_benchmark confirmation after installation.
EOF
}

stop_backend() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "No installer-managed DecisionLab backend is recorded."
    return
  fi
  local pid command
  pid="$(<"$PID_FILE")"
  if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
    echo "The recorded PID is invalid; no process was stopped."
    rm -f "$PID_FILE"
    return
  fi
  command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  if [[ "$command" == *"decisionlab serve"* ]]; then
    kill -TERM "$pid"
    echo "Stopped DecisionLab backend (PID $pid)."
  else
    echo "The recorded PID is stale; no process was stopped."
  fi
  rm -f "$PID_FILE"
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  --stop)
    stop_backend
    exit 0
    ;;
esac

if (( $# > 2 )); then
  usage >&2
  exit 2
fi

for executable in uv npm npx curl; do
  if ! command -v "$executable" >/dev/null 2>&1; then
    echo "Missing required command: $executable" >&2
    exit 1
  fi
done

DATASET_ROOT_INPUT="${1:-$ROOT_DIR/mcp-server/tests/fixtures/inspector}"
DATASET_FOLDER="${2:-sample}"
if [[ ! -d "$DATASET_ROOT_INPUT" ]]; then
  echo "Dataset root does not exist: $DATASET_ROOT_INPUT" >&2
  exit 1
fi
DATASET_ROOT="$(cd -- "$DATASET_ROOT_INPUT" && pwd -P)"
if [[ ! -f "$DATASET_ROOT/$DATASET_FOLDER/dataset.jsonl" ]]; then
  echo "Missing dataset: $DATASET_ROOT/$DATASET_FOLDER/dataset.jsonl" >&2
  exit 1
fi

PORT="${DECISIONLAB_MCP_PORT:-8879}"
if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "DECISIONLAB_MCP_PORT must be a number from 1 to 65535" >&2
  exit 1
fi
BASE_URL="http://127.0.0.1:$PORT"
DATA_ROOT="${DECISIONLAB_MCP_DATA_ROOT:-$CACHE_DIR/data}"
mkdir -p "$CACHE_DIR" "$DATA_ROOT"

cd "$ROOT_DIR"
echo "Installing DecisionLab dependencies..."
uv sync --locked --inexact
npm ci
uv sync --directory mcp-server --inexact

echo "Running offline verification..."
.venv/bin/python -m pytest -q
uv run --directory mcp-server pytest -q
npm test
npm run build

STARTED_PID=""
cleanup_failed_install() {
  local status=$?
  if (( status != 0 )) && [[ -n "$STARTED_PID" ]]; then
    kill -TERM "$STARTED_PID" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  return "$status"
}
trap cleanup_failed_install EXIT

health="$(curl -fsS "$BASE_URL/api/v1/health" 2>/dev/null || true)"
if [[ "$health" == *'"status":"ok"'* ]]; then
  echo "Reusing DecisionLab at $BASE_URL."
else
  if [[ -f "$PID_FILE" ]] && kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
    echo "An installer-managed process is running but $BASE_URL is unhealthy." >&2
    echo "Run ./install-mcp.sh --stop and retry." >&2
    exit 1
  fi
  echo "Starting DecisionLab at $BASE_URL..."
  nohup env DECISIONLAB_DATA_ROOT="$DATA_ROOT" \
    .venv/bin/decisionlab serve --host 127.0.0.1 --port "$PORT" \
    >"$LOG_FILE" 2>&1 &
  STARTED_PID=$!
  printf '%s\n' "$STARTED_PID" >"$PID_FILE"
  for _ in {1..60}; do
    health="$(curl -fsS "$BASE_URL/api/v1/health" 2>/dev/null || true)"
    [[ "$health" == *'"status":"ok"'* ]] && break
    sleep 0.5
  done
  if [[ "$health" != *'"status":"ok"'* ]]; then
    echo "DecisionLab did not become healthy. See $LOG_FILE" >&2
    exit 1
  fi
fi

{
  printf 'export TARGET_API_BASE_URL=%q\n' "$BASE_URL"
  printf 'export DECISIONLAB_DATASET_ROOT=%q\n' "$DATASET_ROOT"
} >"$ENV_FILE"

INSPECTOR=(
  npx -y @modelcontextprotocol/inspector --cli
  uv run --directory mcp-server repo-mcp --
  -e "TARGET_API_BASE_URL=$BASE_URL"
  -e "DECISIONLAB_DATASET_ROOT=$DATASET_ROOT"
)

echo "Verifying the MCP tool surface..."
"${INSPECTOR[@]}" --method tools/list --format json >"$CACHE_DIR/tools.json"
tool_count="$(.venv/bin/python -c \
  'import json, sys; print(len(json.load(open(sys.argv[1]))["result"]["tools"]))' \
  "$CACHE_DIR/tools.json")"
if [[ "$tool_count" != "6" ]]; then
  echo "Expected 6 MCP tools, found $tool_count" >&2
  exit 1
fi

tool_args="$(.venv/bin/python -c \
  'import json, sys; print(json.dumps({"dataset_folder": sys.argv[1], "profile": "standard", "publication": False}))' \
  "$DATASET_FOLDER")"
echo "Preparing '$DATASET_FOLDER' without provider calls..."
"${INSPECTOR[@]}" \
  --method tools/call \
  --tool-name prepare_benchmark \
  --tool-args-json "$tool_args" \
  --format json >"$CACHE_DIR/prepare-result.json"

echo
echo "DecisionLab MCP is installed and the free smoke test passed."
echo "Backend: $BASE_URL"
echo "Environment: $ENV_FILE"
echo "Prepared workflow: $CACHE_DIR/prepare-result.json"
echo "Backend log: $LOG_FILE"
echo
echo "Before starting Codex or Inspector in another terminal, run:"
printf '  source %q\n' "$ENV_FILE"
echo "Stop the installer-managed backend with: ./install-mcp.sh --stop"
