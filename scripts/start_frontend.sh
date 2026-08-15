#!/usr/bin/env bash
# Start the Streamlit frontend
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "Starting AegisCode Frontend..."
streamlit run frontend/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0
