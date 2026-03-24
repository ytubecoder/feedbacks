#!/bin/bash
# Feedbacks — single command launcher
# Usage: ./start.sh [whisper-model-path]
# Starts whisper-server + HTTP server, prints URL

set -e

MODEL="${1:-models/ggml-base.bin}"
WHISPER_PORT=8081
APP_PORT=8080

# Find whisper-server
if command -v whisper-server &>/dev/null; then
  WHISPER_CMD="whisper-server"
elif [ -f ./whisper-server ]; then
  WHISPER_CMD="./whisper-server"
elif [ -f ./whisper.cpp/build/bin/whisper-server ]; then
  WHISPER_CMD="./whisper.cpp/build/bin/whisper-server"
else
  echo "whisper-server not found."
  echo ""
  echo "Install whisper.cpp:"
  echo "  git clone https://github.com/ggerganov/whisper.cpp"
  echo "  cd whisper.cpp && cmake -B build && cmake --build build -j --config Release"
  echo ""
  echo "Download a model:"
  echo "  ./whisper.cpp/models/download-ggml-model.sh base"
  echo ""
  echo "Then run again: ./start.sh whisper.cpp/models/ggml-base.bin"
  exit 1
fi

# Check model exists
if [ ! -f "$MODEL" ]; then
  echo "Model not found: $MODEL"
  echo ""
  echo "Download one:"
  echo "  # From whisper.cpp directory:"
  echo "  ./models/download-ggml-model.sh base"
  echo ""
  echo "Then: ./start.sh path/to/ggml-base.bin"
  exit 1
fi

# Cleanup on exit
cleanup() {
  echo ""
  echo "Shutting down..."
  kill $WHISPER_PID $HTTP_PID 2>/dev/null
  wait $WHISPER_PID $HTTP_PID 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

# Start whisper-server
echo "Starting whisper-server on :$WHISPER_PORT..."
$WHISPER_CMD -m "$MODEL" --port $WHISPER_PORT --host 127.0.0.1 --inference-path "/v1/audio/transcriptions" &
WHISPER_PID=$!

# Start HTTP server for the app
echo "Starting app server on :$APP_PORT..."
python3 -m http.server $APP_PORT --bind 127.0.0.1 &
HTTP_PID=$!

# Wait for whisper to be ready
echo -n "Waiting for whisper-server"
for i in {1..15}; do
  if curl -sf http://localhost:$WHISPER_PORT/health >/dev/null 2>&1; then
    echo " ready!"
    break
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "================================"
echo "  Feedbacks is running!"
echo "  Open: http://localhost:$APP_PORT"
echo "  Press Ctrl+C to stop"
echo "================================"
echo ""

wait
