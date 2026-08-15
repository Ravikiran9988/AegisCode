#!/usr/bin/env bash
# Start the FastAPI backend with hot-reload
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "Starting AegisCode Backend..."
uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir backend \
    --log-level info
