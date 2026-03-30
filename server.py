#!/usr/bin/env python3
"""Feedbacks server — static files + session save endpoint.

Usage:
    FEEDBACKS_OUTPUT_DIR=./sessions python3 server.py [--port 8080]

Endpoints:
    GET  /           — serves index.html and static files
    GET  /config     — returns JSON with output directory path
    POST /save       — saves session files to output directory
"""

import http.server
import json
import base64
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = 8080
OUTPUT_DIR = os.environ.get("FEEDBACKS_OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "sessions"))


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
        self.send_error(404)

    def _handle_save(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            # Expected shape:
            # { "name": "feedbacks-2026-03-30-123456",
            #   "markdown": "...",
            #   "player": "...",
            #   "images": [{"filename": "001.png", "base64": "..."}] }

            name = data.get("name", "session")
            session_dir = Path(OUTPUT_DIR) / name
            images_dir = session_dir / "images"
            images_dir.mkdir(parents=True, exist_ok=True)

            # Write markdown
            (session_dir / "session.md").write_text(data["markdown"], encoding="utf-8")

            # Write player
            (session_dir / "player.html").write_text(data["player"], encoding="utf-8")

            # Write images
            for img in data.get("images", []):
                img_bytes = base64.b64decode(img["base64"])
                (images_dir / img["filename"]).write_bytes(img_bytes)

            saved_path = str(session_dir.resolve())
            print(f"Session saved to: {saved_path}")
            self._send_json({"ok": True, "path": saved_path})

        except Exception as e:
            print(f"Save error: {e}")
            self._send_json({"ok": False, "error": str(e)}, status=500)

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
        # Quieter logging — skip static file requests
        if args and isinstance(args[0], str) and args[0].startswith("GET /"):
            return
        super().log_message(format, *args)


def main():
    port = PORT
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--port" and i + 2 < len(sys.argv):
            port = int(sys.argv[i + 2])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {Path(OUTPUT_DIR).resolve()}")
    print(f"Serving on http://127.0.0.1:{port}")

    server = http.server.HTTPServer(("127.0.0.1", port), FeedbacksHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
