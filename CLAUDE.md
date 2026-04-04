# Feedbacks — Project Guide

## Architecture

Single-page browser app (`index.html`) + Python server (`server.py`) + whisper.cpp for local STT.

### Key Components

- **`index.html`** — Complete app: capture, VAD, transcription, timeline UI, save output, player generation
- **`server.py`** — All-in-one launcher: starts whisper-server (with Silero VAD), serves app, provides `/save`, `/transcribe` proxy, `/sessions` API with parsed timeline data, `/live-push` + `/live-session` for real-time MCP bridge
- **`mcp_server.py`** — Stdio MCP server: `feedbacks_sessions` / `feedbacks_session` for browsing saved sessions, `feedbacks_status` / `feedbacks_poll` for live capture streaming into Claude Code
- **`start.sh`** — Thin wrapper that calls `server.py`
- **`whisper.cpp/`** — Git submodule, built locally for speech-to-text
- **`skills/feedbacks/`** — Claude Code skill (copied to `~/.claude/skills/feedbacks/` for global access)

### How It Works

1. `getDisplayMedia` captures screen (VideoFrame API for actual pixel access — `drawImage` produces black on Chrome)
2. Auto-captures screenshots every 1s with dedup (horizontal strip comparison, force-capture every 5s)
3. **Voice Activity Detection (VAD)** in the WebAudio analyser RAF loop detects speech start/end
4. Audio chunks are driven by speech boundaries (not fixed intervals) — whisper only receives audio containing speech
5. `/transcribe` proxy converts WebM→WAV via ffmpeg, forwards to whisper-server
6. Anti-hallucination stack: no prompt seeding, blocklist, repeat detection
7. Output saved to `sessions/` as extracted files (session.md, player.html, images/) with speech-span grouping
8. **Live MCP bridge** — during capture, events are also pushed to `/live-push` in real-time. The `mcp_server.py` exposes `feedbacks_status()` and `feedbacks_poll()` tools so Claude Code can receive the timeline live (screenshots as file paths in `/tmp/feedbacks-live/`, transcripts inline, grouped by speech spans)

### MCP Server

Registered via `claude mcp add feedbacks -- python3 $(pwd)/mcp_server.py`. Requires `pip install mcp`.

**Saved session tools** (read from disk, no server needed):
- **`feedbacks_sessions()`** — list all sessions with dates, durations, ticket IDs, AI summaries
- **`feedbacks_session(name)`** — full timeline for one session: metadata + screenshots as absolute file paths + transcripts

**Live capture tools** (require `server.py` running):
- **`feedbacks_status()`** — check if capture is active
- **`feedbacks_poll(since=0)`** — get timeline-grouped events (speech spans with screenshots + transcripts). Pass `latestSeqNum` from previous poll for incremental updates. Speech span events are always included regardless of `since` to maintain grouping.
- Use `/feedbacks watch` skill command to start watching a live capture
- Screenshots written to `/tmp/feedbacks-live/{sessionId}/images/` — Claude reads them with the Read tool
- Session ID matches the final saved directory name (`sessions/{sessionId}/`)

**Server instructions** are provided via the MCP `instructions` field in `FastMCP()` — auto-injected into Claude Code's context at session start.

### UI Structure

- **Session list** — past sessions as expandable cards with hero thumbnails, status badges, AI summaries
- **Capture prompt** — split button: main "New Capture" goes straight to screen share, dropdown ▾ for ticket ID
- **Live recording** — timeline feed with IMG/STT entries, green speaking indicator, mic level meter
- **Expanded detail** — vertical timeline spine with screenshot+transcript pairs, context frames collapsed

### Anti-Hallucination Stack

1. Client-side VAD — don't record silence (WebAudio energy threshold + onset/offset delays)
2. Server-side Silero VAD — whisper-server `--vad` flag rejects non-speech audio
3. No prompt seeding — previous transcript not fed back (prevents cascade hallucinations)
4. Blocklist — known phantom phrases dropped (`HALLUCINATION_BLOCKLIST` in index.html)
5. Repeat detection — same text 3+ times in a chunk → entire chunk discarded, `⚠ Filtered` shown in timeline

See `docs/decisions/001-whisper-initial-prompt.md` for full rationale.

## Running

```bash
cd ~/projects/feedbacks && python3 server.py
# Automatically starts whisper (prefers small.en model + Silero VAD), serves on :8080
```

## Known Issues

- **VideoFrame API required** — `canvas.drawImage(video)` from getDisplayMedia produces black frames on Chrome. Uses `MediaStreamTrackProcessor` + `VideoFrame` instead.
- **WebM→WAV conversion** — whisper.cpp doesn't accept WebM/Opus. The `/transcribe` proxy converts via ffmpeg.
- **Cross-tab interaction** — User interacts with the shared tab, not the feedbacks page. Keyboard hotkeys can't reach feedbacks from the observed app. VAD (audio-level speech detection) is the only zero-friction input method.
- **VAD threshold tuning** — `SPEECH_THRESHOLD = 25` may need adjustment for different microphones/environments. Too low = background noise triggers. Too high = quiet speech missed.
- **Whisper accuracy** — Even with small.en + VAD, whisper can mishear words. The transcript is always the raw whisper output, never modified. AI summary is generated separately by Claude.
- **WSL access** — `getDisplayMedia`/`getUserMedia` require secure context. Access via WSL IP fails silently. Use Chrome `--unsafely-treat-insecure-origin-as-secure` flag or forward to localhost.

## Output Directory

Default: `./sessions/`. Override: `FEEDBACKS_OUTPUT_DIR=/path/to/dir python3 server.py`

Each session saves to `sessions/feedbacks-{timestamp}/` with: `session.md`, `player.html`, `images/`, `debug.log`, `meta.json`, `summary.json`

## Ticket Integration

Optional `?ticket=B-05` query param links sessions to tickets. The `/review` skill from ticket-takeaway can pick up sessions from `docs/features/{ID}/feedbacks/`. See README.md for details.
