#!/usr/bin/env python3
"""Feedbacks server — all-in-one launcher.

Usage:
    python3 server.py [--port 8080] [--whisper-port 8081] [--no-whisper]

Starts whisper-server (auto-detected) + HTTP server with save endpoint.
Set FEEDBACKS_OUTPUT_DIR to control where sessions are saved.
"""

import http.server
import json
import base64
import os
import sys
import signal
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
PORT = 8080
WHISPER_PORT = 8081
OUTPUT_DIR = os.environ.get("FEEDBACKS_OUTPUT_DIR", str(SCRIPT_DIR / "sessions"))

whisper_process = None


# ── Whisper management ──

def find_whisper_server():
    """Find whisper-server binary."""
    candidates = [
        SCRIPT_DIR / "whisper.cpp" / "build" / "bin" / "whisper-server",
        SCRIPT_DIR / "whisper-server",
        Path("whisper-server"),  # on PATH
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # Check PATH
    import shutil
    found = shutil.which("whisper-server")
    if found:
        return found
    return None


def find_whisper_model():
    """Find a whisper model file."""
    candidates = [
        SCRIPT_DIR / "whisper.cpp" / "models" / "ggml-small.en.bin",
        SCRIPT_DIR / "whisper.cpp" / "models" / "ggml-base.en.bin",
        SCRIPT_DIR / "whisper.cpp" / "models" / "ggml-base.bin",
        SCRIPT_DIR / "whisper.cpp" / "models" / "ggml-tiny.en.bin",
        SCRIPT_DIR / "models" / "ggml-small.en.bin",
        SCRIPT_DIR / "models" / "ggml-base.en.bin",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # Glob for any model
    for pattern in ["whisper.cpp/models/ggml-*.bin", "models/ggml-*.bin"]:
        found = list(SCRIPT_DIR.glob(pattern))
        if found:
            return str(found[0])
    return None


def check_whisper_health(port, timeout=2):
    """Check if whisper-server is already running."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False


def install_whisper():
    """Attempt to install whisper.cpp automatically."""
    whisper_dir = SCRIPT_DIR / "whisper.cpp"

    if not whisper_dir.exists():
        print("Installing whisper.cpp...")
        subprocess.run(
            ["git", "clone", "https://github.com/ggerganov/whisper.cpp"],
            cwd=str(SCRIPT_DIR), check=True
        )

    build_dir = whisper_dir / "build"
    server_bin = build_dir / "bin" / "whisper-server"

    if not server_bin.exists():
        print("Building whisper.cpp...")
        subprocess.run(["cmake", "-B", "build"], cwd=str(whisper_dir), check=True)
        subprocess.run(
            ["cmake", "--build", "build", "-j", "--config", "Release"],
            cwd=str(whisper_dir), check=True
        )

    if not server_bin.exists():
        raise RuntimeError("whisper-server build failed")

    # Download model if needed
    model = find_whisper_model()
    if not model:
        print("Downloading base.en model...")
        download_script = whisper_dir / "models" / "download-ggml-model.sh"
        if download_script.exists():
            subprocess.run(
                ["bash", str(download_script), "base.en"],
                cwd=str(whisper_dir), check=True
            )
        else:
            raise RuntimeError("No model found and download script missing")

    return str(server_bin), find_whisper_model()


def start_whisper(port):
    """Start whisper-server, installing if needed. Returns subprocess or None."""
    global whisper_process

    # Already running?
    if check_whisper_health(port):
        print(f"Whisper already running on :{port}")
        return None

    server_bin = find_whisper_server()
    model = find_whisper_model()

    # Auto-install if missing
    if not server_bin or not model:
        try:
            server_bin, model = install_whisper()
        except Exception as e:
            print(f"Whisper auto-install failed: {e}")
            print("Continuing without local STT — use OpenAI API key in the UI as fallback")
            return None

    print(f"Starting whisper-server on :{port} with {Path(model).name}...")
    whisper_process = subprocess.Popen(
        [server_bin, "-m", model, "--port", str(port),
         "--host", "127.0.0.1", "--inference-path", "/v1/audio/transcriptions"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    # Wait for it to come up
    print("Waiting for whisper-server", end="", flush=True)
    for _ in range(20):
        if whisper_process.poll() is not None:
            print(f" FAILED (exit code {whisper_process.returncode})")
            whisper_process = None
            print("Continuing without local STT")
            return None
        if check_whisper_health(port, timeout=1):
            print(" ready!")
            return whisper_process
        print(".", end="", flush=True)
        time.sleep(1)

    print(" timeout — continuing without local STT")
    return whisper_process


def stop_whisper():
    """Stop whisper-server if we started it."""
    global whisper_process
    if whisper_process:
        print("Stopping whisper-server...")
        whisper_process.terminate()
        try:
            whisper_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            whisper_process.kill()
        whisper_process = None


# ── HTTP handler ──

class FeedbacksHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/config":
            self._send_json({"outputDir": str(Path(OUTPUT_DIR).resolve())})
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/save":
            self._handle_save()
            return
        if self.path == "/transcribe":
            self._handle_transcribe()
            return
        self.send_error(404)

    def _handle_save(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            name = data.get("name", "session")
            session_dir = Path(OUTPUT_DIR) / name
            images_dir = session_dir / "images"
            images_dir.mkdir(parents=True, exist_ok=True)

            (session_dir / "session.md").write_text(data["markdown"], encoding="utf-8")
            (session_dir / "player.html").write_text(data["player"], encoding="utf-8")

            if data.get("log"):
                (session_dir / "debug.log").write_text(data["log"], encoding="utf-8")

            for img in data.get("images", []):
                img_bytes = base64.b64decode(img["base64"])
                (images_dir / img["filename"]).write_bytes(img_bytes)

            saved_path = str(session_dir.resolve())
            print(f"Session saved to: {saved_path}")
            self._send_json({"ok": True, "path": saved_path})

        except Exception as e:
            print(f"Save error: {e}")
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _handle_transcribe(self):
        """Proxy transcription: convert WebM→WAV via ffmpeg, forward to whisper."""
        import tempfile
        import cgi

        try:
            content_type = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", 0))

            # Parse multipart using cgi.FieldStorage
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(length),
            }
            form = cgi.FieldStorage(
                fp=self.rfile, headers=self.headers, environ=environ
            )

            # Extract audio file
            file_item = form["file"]
            audio_data = file_item.file.read()
            filename = file_item.filename or "chunk.webm"

            # Extract other form fields
            other_fields = {}
            for key in form:
                if key != "file":
                    other_fields[key] = form.getvalue(key)

            if not audio_data or len(audio_data) < 100:
                self._send_json({"error": f"Audio too small: {len(audio_data)}B"}, status=400)
                return

            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = os.path.join(tmpdir, filename)
                output_path = os.path.join(tmpdir, "audio.wav")

                with open(input_path, "wb") as f:
                    f.write(audio_data)

                # Convert to WAV (16kHz mono, what whisper expects)
                result = subprocess.run(
                    ["ffmpeg", "-i", input_path, "-ar", "16000", "-ac", "1",
                     "-f", "wav", output_path, "-y"],
                    capture_output=True, timeout=10
                )

                if result.returncode != 0:
                    err = result.stderr.decode("utf-8", errors="replace")[-300:]
                    print(f"ffmpeg failed (code {result.returncode}):\n{err}")
                    self._send_json({"error": f"ffmpeg failed: {err[-150:]}"}, status=500)
                    return

                # Forward to whisper as WAV multipart
                wav_boundary = "----WavBoundary9876"
                with open(output_path, "rb") as f:
                    wav_data = f.read()

                parts = []
                parts.append(f"--{wav_boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode())
                parts.append(wav_data)
                parts.append(b"\r\n")

                for key, val in other_fields.items():
                    parts.append(f"--{wav_boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{val}\r\n".encode())

                parts.append(f"--{wav_boundary}--\r\n".encode())
                body_bytes = b"".join(parts)

                whisper_url = f"http://127.0.0.1:{WHISPER_PORT}/v1/audio/transcriptions"
                req = urllib.request.Request(
                    whisper_url, data=body_bytes,
                    headers={"Content-Type": f"multipart/form-data; boundary={wav_boundary}"},
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=30) as resp:
                    response_data = resp.read()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(response_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": str(e)}, status=500)

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        if args and isinstance(args[0], str) and args[0].startswith("GET /"):
            return
        super().log_message(format, *args)


# ── Main ──

def main():
    port = PORT
    whisper_port = WHISPER_PORT
    skip_whisper = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1]); i += 2
        elif args[i] == "--whisper-port" and i + 1 < len(args):
            whisper_port = int(args[i + 1]); i += 2
        elif args[i] == "--no-whisper":
            skip_whisper = True; i += 1
        else:
            i += 1

    # Handle clean shutdown
    def shutdown(sig, frame):
        stop_whisper()
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Start whisper
    if not skip_whisper:
        start_whisper(whisper_port)
    else:
        print("Whisper disabled (--no-whisper)")

    print()
    print("================================")
    print("  Feedbacks is running!")
    print(f"  Open: http://localhost:{port}")
    print(f"  Sessions save to: {Path(OUTPUT_DIR).resolve()}")
    print(f"  Whisper: {'http://localhost:' + str(whisper_port) if not skip_whisper else 'disabled'}")
    print("  Press Ctrl+C to stop")
    print("================================")
    print()

    server = http.server.HTTPServer(("127.0.0.1", port), FeedbacksHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_whisper()
        server.server_close()


if __name__ == "__main__":
    main()
