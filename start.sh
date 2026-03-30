#!/bin/bash
# Feedbacks — single command launcher
# Usage: ./start.sh
# Starts whisper-server + HTTP server with auto-save

set -e
cd "$(dirname "$0")"
export FEEDBACKS_OUTPUT_DIR="${FEEDBACKS_OUTPUT_DIR:-./sessions}"
exec python3 server.py "$@"
