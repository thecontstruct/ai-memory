#!/usr/bin/env bash
# Run memory scripts with proper environment variables
# Usage: ./scripts/memory/run-with-env.sh <script.py> [args...]
#
# This script loads QDRANT_API_KEY and other env vars from docker/.env
# Required because scripts run on HOST need the same auth as Docker services
# and must use the ai-memory virtualenv rather than the shell's default python3.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${AI_MEMORY_INSTALL_DIR:-$HOME/.ai-memory}"
ENV_FILE="${AI_MEMORY_ENV_FILE:-$INSTALL_DIR/docker/.env}"
PY_BIN="$INSTALL_DIR/.venv/bin/python"

export QDRANT_HOST="${QDRANT_HOST:-localhost}"
export QDRANT_PORT="${QDRANT_PORT:-26350}"
export QDRANT_GRPC_PORT="${QDRANT_GRPC_PORT:-26351}"
export EMBEDDING_HOST="${EMBEDDING_HOST:-127.0.0.1}"
export QDRANT_USE_HTTPS="${QDRANT_USE_HTTPS:-false}"

load_env_var() {
    local name="$1"
    local value
    value="$(awk -F= -v key="$name" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$ENV_FILE")"
    # Strip surrounding double or single quotes (common in .env files)
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    if [ -n "$value" ]; then
        export "$name=$value"
    fi
}

# Load environment variables from docker/.env
if [ -f "$ENV_FILE" ]; then
    load_env_var "QDRANT_API_KEY"
    load_env_var "AI_MEMORY_PROJECT_ID"
    load_env_var "GITHUB_REPO"
    load_env_var "GITHUB_BRANCH"
    load_env_var "GITHUB_TOKEN"
    load_env_var "GITHUB_SYNC_ENABLED"
else
    echo "Warning: $ENV_FILE not found, running without API key"
fi

if [ ! -x "$PY_BIN" ]; then
    echo "Error: ai-memory venv python not found: $PY_BIN"
    echo "Run $INSTALL_DIR/scripts/install.sh or set AI_MEMORY_INSTALL_DIR correctly."
    exit 1
fi

# Check if script argument provided
if [ -z "$1" ]; then
    echo "Usage: $0 <script.py> [args...]"
    echo ""
    echo "Available scripts:"
    for script_path in "$SCRIPT_DIR"/*.py; do
        [ -e "$script_path" ] || continue
        basename "$script_path"
    done
    exit 1
fi

SCRIPT="$1"
shift

# If script doesn't have full path, look in scripts/memory/
if [ ! -f "$SCRIPT" ]; then
    SCRIPT="$SCRIPT_DIR/$SCRIPT"
fi

if [ ! -f "$SCRIPT" ]; then
    echo "Error: Script not found: $SCRIPT"
    exit 1
fi

# Run the script
exec "$PY_BIN" "$SCRIPT" "$@"
