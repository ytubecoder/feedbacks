# Feedbacks — Project Guide

## Architecture

Single-page browser app (`index.html`) + Python server (`server.py`) + whisper.cpp for local STT.

### Key Components

- **`index.html`** — Complete app: capture, transcription, timeline UI, ZIP/save output, player generation
- **`server.py`** — All-in-one launcher: starts whisper-server, serves app, provides `/save` and `/transcribe` proxy endpoints
- **`start.sh`** — Thin wrapper that calls `server.py`
- **`whisper.cpp/`** — Git submodule, built locally for speech-to-text

### How It Works

1. `getDisplayMedia` captures screen (VideoFrame API for actual pixel access — `drawImage` produces black on Chrome)
2. Auto-captures screenshots every 1s with dedup (full-width horizontal strip comparison, force-capture every 5s)
3. `MediaRecorder` records mic in 10s chunks, sent to `/transcribe` proxy which converts WebM→WAV via ffmpeg then forwards to whisper
4. Output saved to `sessions/` directory as extracted files (session.md, player.html, images/) + optional ZIP download

### Three-State UI

- **Setup** — Readiness checks (STT status, mic level meter), Start button
- **Recording** — Compact header + status strip + scrolling timeline (IMG + STT entries with placeholder pattern)
- **Done** — Header swaps to done bar with copy-path/ZIP/New Session; timeline stays visible

## Running

```bash
cd ~/projects/feedbacks && python3 server.py
# Automatically starts whisper (prefers small.en model), serves on :8080
```

## Known Issues

- **VideoFrame API required** — `canvas.drawImage(video)` from getDisplayMedia produces black frames on Chrome. The app uses `MediaStreamTrackProcessor` + `VideoFrame` to read frames directly from the stream.
- **WebM→WAV conversion** — whisper.cpp doesn't accept WebM/Opus natively. The `/transcribe` proxy converts via ffmpeg.
- **Dedup sensitivity** — Samples a horizontal strip from the middle of the frame. Static pages with no cursor movement get deduped. Force-capture every 5s ensures minimum coverage.
- **Cross-tab interaction** — User interacts with the shared tab, not the feedbacks page. Click-to-mark doesn't work cross-tab. Auto-capture with cursor baked into frames is the capture strategy.

## Output Directory

Default: `./sessions/`. Override: `FEEDBACKS_OUTPUT_DIR=/path/to/dir python3 server.py`

Each session saves to `sessions/feedbacks-{timestamp}/` with: `session.md`, `player.html`, `images/`, `debug.log`
