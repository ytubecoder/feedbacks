# Session Log

## 2026-04-03 — MCP server for live capture streaming and session history

### Summary
- Built MCP server (`mcp_server.py`) with 4 tools: `feedbacks_sessions`, `feedbacks_session`, `feedbacks_status`, `feedbacks_poll`
- Added live capture bridge: browser pushes incremental events (screenshots, transcripts, speech spans) to server.py via `/live-push`, MCP server polls `/live-session` to feed Claude Code
- Saved session tools read directly from disk (no server needed), live tools require server.py running
- Cleaned repo for public distribution: removed hardcoded paths, added LICENSE (source-available, commercial requires license), made repo public

### Lessons Learned
- **Accepted:** MCP polling over push — standard MCP is request-response (Claude calls tool, server responds). True server-initiated push isn't reliably supported in Claude Code CLI yet. Polling with incremental sequence numbers works well enough.
- **Accepted:** Speech span events always included in poll responses regardless of `since` filter — without them, incremental polls can't group screenshots with transcripts. Structural events must bypass the filter.
- **Accepted:** Saved session tools reading directly from disk rather than through HTTP — works even when server.py isn't running, which is the common case for reviewing past sessions.
- **Accepted:** FastMCP `instructions` parameter for server-level context — gets injected into Claude's system prompt at session start, so Claude knows what the tools are for without needing the skill invoked.
- **Rejected:** SSE/WebSocket MCP transport for true streaming — uncertain support in Claude Code CLI today. The server.py plumbing is the same either way; only the MCP transport layer would change.
- **Rejected:** MCP resource subscriptions — theoretically push-based, but Claude Code's handling of unsolicited resource notifications is unreliable.
- **Gotcha:** FastMCP constructor doesn't accept `version` parameter (unlike docs/examples suggest) — just `name` and `instructions`.
- **Gotcha:** `pip install mcp` fails on system Python without `--break-system-packages` on Ubuntu/Debian with PEP 668 enforcement.
- **Gotcha:** Mid-speech capture end leaves an unclosed speech span — must synthesize a closing span in `_build_timeline` using the max event time.

### Decisions
- MCP server is a separate file (`mcp_server.py`) not integrated into `server.py` — keeps concerns separate, MCP server can work without HTTP server for saved sessions.
- Screenshots stored as files in `/tmp/feedbacks-live/` during live capture, returned as absolute paths in MCP responses — avoids bloating tool responses with base64 (200KB+ per screenshot).
- Fire-and-forget for browser live-push (`fetch().catch(() => {})`) — live push must never block/slow the capture experience. Missing events are acceptable.
- License changed from MIT to source-available: free for personal/non-commercial, commercial use requires separate license.
- Repo made public on GitHub.

## 2026-03-31/04-01 — VAD, anti-hallucination stack, ticket integration, UI polish

### Summary
- Voice Activity Detection: speech-driven audio chunks replace fixed 10-second intervals. WebAudio energy analysis in RAF loop with onset/offset delays.
- Anti-hallucination stack: removed prompt seeding, added blocklist (20 known phrases), repeat detection (3+ same text drops chunk). Filtered entries visible in timeline with ⚠ marker.
- Ticket integration: `?ticket=B-05` query param, split capture button, status badges, /review skill integration for visual bug reporting.
- UI redesign: shadcn zinc dark theme, vertical timeline spine in detail view, speech-anchored session.md grouping.
- Literal summary prompt: Claude describes visible content only, not inferred actions.

### Lessons Learned
- **Accepted:** VAD via WebAudio frequency energy — the mic analyser was already running at 60fps for the level meter. Adding speech detection was ~30 lines of state machine code in the same RAF loop.
- **Accepted:** Speech-driven chunks over fixed 10s intervals — sending only speech to whisper eliminates hallucinations at the source. More effective than any post-transcription filtering.
- **Rejected:** Keyboard hotkeys for PTT — browser can't receive keystrokes when the observed app has focus. Audio-level VAD is the only zero-friction approach in a browser-only architecture.
- **Rejected:** Sending previous transcript as whisper prompt (condition_on_previous_text) — hallucinated text cascades into next chunk's prompt, creating 28x repetition loops. Marginal continuity benefit not worth the cascade risk.
- **Rejected:** VibeVoice (Microsoft) as whisper alternative — 7B params, needs 24GB VRAM GPU. Overkill for 10-second single-speaker chunks. whisper.cpp small.en is the right tool.
- **Gotcha:** whisper initial_prompt "User is describing what they see on screen" was being parroted as transcript on quiet audio. The prompt text literally became the transcription output.
- **Gotcha:** Browser caching of index.html — after code changes, server restart alone doesn't push new JS to the browser. Users must Ctrl+Shift+R to hard refresh.

### Decisions
- VAD SPEECH_THRESHOLD = 25, onset 300ms, offset 1500ms — empirically tuned. May need per-microphone adjustment.
- Hallucination blocklist is hardcoded in index.html (not external file) — 20 entries, maintainable inline. Decision doc at docs/decisions/001-whisper-initial-prompt.md.
- Session.md groups by speech spans when available, falls back to midpoint-assignment for pre-VAD sessions.
- AI summary prompt explicitly forbids inference ("don't say user searched for X unless search action visible").
- Feedbacks skill shipped from repo (`skills/feedbacks/`) with install instructions in README.

## 2026-03-30/31 — Fix black screen, add auto-save, redesign UI

### Summary
- Fixed black screen capture bug (VideoFrame API replaces canvas.drawImage which produces black on Chrome)
- Added server.py with auto-save to disk, whisper auto-start, and WebM→WAV transcription proxy
- Upgraded whisper model from base.en to small.en with context prompting
- Complete UI redesign: three-state layout (Setup → Recording → Done) with timeline-centric recording view, mic level meter, status strip, and STT placeholder pattern
- Added auto-capture every 1s with dedup (horizontal strip sampling + 5s force-capture)

### Lessons Learned
- **Accepted:** VideoFrame API via MediaStreamTrackProcessor — bypasses Chrome's GPU compositor isolation that makes drawImage return black pixels from getDisplayMedia streams
- **Accepted:** WebM→WAV proxy via ffmpeg — whisper.cpp server doesn't accept WebM/Opus, but browser MediaRecorder only outputs WebM. Server-side conversion is simpler than browser-side.
- **Accepted:** Auto-capture with dedup over click-to-capture — user is on a different tab, can't click on the feedbacks preview. Cursor position is baked into the captured frame by getDisplayMedia cursor:always.
- **Rejected:** Corner-based dedup sampling (5 fixed 32x32 patches) — corners are typically browser chrome/margins that don't change. Full-width horizontal strip from center catches scrolling and cursor movement.
- **Rejected:** Keyboard shortcuts for capture (press S) — keystrokes go to the shared tab, not the feedbacks page.
- **Rejected:** MediaRecorder start(1000) timeslice — produces continuation chunks without WebM headers. Only the first chunk is a valid standalone file. Use start() without timeslice instead.
- **Gotcha:** `micStream` vs `micStreamRef` — global `micStream` was never assigned, only `micStreamRef`. Caused rotateChunk to fail silently on chunks 2+.
- **Gotcha:** stopSession set isRecording=false before captureScreenshot, which early-returned. Must capture before clearing the flag.
- **Gotcha:** cgi.FieldStorage needed for multipart parsing — manual boundary split was fragile and broke on subsequent requests.

### Decisions
- Timeline stays visible after session ends (done bar replaces header, timeline persists)
- STT entries get "transcribing..." placeholder at chunk start time, replaced when whisper responds (keeps timeline in chronological order)
- Force-capture every 5s even if dedup says no change (minimum coverage guarantee)
- small.en whisper model preferred over base.en (3x more accurate, acceptable latency for 10s chunks)
