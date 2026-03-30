# Feedbacks UI Redesign — Design Spec

## Goal

Reorganize the feedbacks capture UI from a feature-accumulated layout into a clean, timeline-centric recording interface. The primary user is someone recording feedback (not reviewing it — the LLM agent consumes the output). They need confidence that capture is working, not detailed controls.

## Three States

The UI has three distinct states with different layouts:

### 1. Setup (Pre-Recording)

Centered, minimal. Shows readiness checks before allowing recording to start.

**Layout:**
- Title + subtitle (centered)
- Readiness checklist (vertical stack, centered):
  - **STT status**: Green dot + "Local (small.en)" or "Cloud" or red "No STT"
  - **Microphone**: Green dot + live level meter (animated bars from AudioContext analyser). Requests mic permission on page load to show level before recording.
  - Optional: OpenAI API key input (shown only if STT is offline)
- Ticket ID input (optional, small)
- **Start Session** button (large, green, centered)

**Behavior:**
- Mic permission requested on page load (not on Start click) so the level meter works immediately
- Start button disabled until at least mic is confirmed working
- Whisper health check runs every 5s as before

### 2. Recording

Timeline-centric. Controls compress to a thin header. The timeline feed is the entire page.

**Header bar** (fixed/sticky, thin):
- Left: Stop button (red), recording indicator (pulsing red dot + elapsed time), mini mic level bars
- Right: Stats pills (X img, X/X stt)

**Status strip** (below header):
- Row of colored pills showing live system health:
  - `STT local` (green) / `STT cloud` (blue) / `STT off` (red)
  - `Mic` + mini level bars (green/red)
  - `Capture WxH` (green)
  - `X img` count (blue)
  - `X/X stt` progress (blue)
  - `X deduped` (gray)

**Timeline feed** (scrollable, fills remaining space):
- Entries in chronological order, each with:
  - Timestamp (monospace, left-aligned)
  - Type badge: `IMG` (green) or `STT` (blue)
  - Content: screenshot thumbnail (160-180px wide) or transcript text
- **STT placeholder**: When an audio chunk starts processing, insert a placeholder entry at the chunk's start timestamp with "transcribing..." in italic/dimmed. Replace with actual text when whisper responds. This keeps timeline in chronological order even though STT arrives late.
- Auto-scrolls to bottom as new entries appear

**Diagnostics** (collapsed, bottom of page):
- `<details>` element with summary "Diagnostics"
- One-line summary: VideoFrame WxH | Mic active | Chunk N | Dedup: N skipped | Black: OK
- Expandable for full debug log

**Removed elements:**
- Preview video container (cross-tab clicking doesn't work, auto-capture handles everything)
- Click hint text
- Hotkey hint
- Capture Test Panel (info moved to status strip + diagnostics)
- Retro ticket prompt (ticket set before recording)

### 3. Done (Post-Recording)

Centered completion screen.

**Layout:**
- "Session Saved" heading (green)
- Summary line: "X screenshots, X transcript chunks, M:SS duration"
- **Output path** (monospace, in a bordered box) with **copy button** — clicking copies path to clipboard, shows "Copied!" for 2 seconds
- Action buttons: "Download ZIP" (blue) + "New Session" (green)

## Live Timeline Implementation

### Entry insertion
- Screenshots: Appended to timeline immediately when captured (already synchronous relative to timeline)
- Transcripts: Insert a placeholder `<div>` at the chunk's `offsetTime` when `rotateChunk()` fires. Give it a data attribute with the chunk number. When `transcribeChunk()` completes, find the placeholder by chunk number and replace its content with the actual text.

### Ordering
- All entries have a `data-timestamp` attribute
- New entries inserted in sorted order (find the right position, not just append)
- For auto-scroll: only scroll to bottom if user hasn't manually scrolled up

## Mic Level Meter

- Use `AudioContext` + `AnalyserNode` connected to the mic stream
- `getByteFrequencyData()` in a `requestAnimationFrame` loop
- Render as 5 small bars at different heights based on frequency bins
- Two sizes: large (setup screen, ~14px tall) and mini (recording header, ~10px tall)
- Green when signal detected, gray when silent
- Request mic permission on page load for the setup screen meter

## Clipboard Copy

- `navigator.clipboard.writeText(path)` on click
- Visual feedback: button text changes to "Copied!" for 2 seconds, then reverts
- Fallback: `document.execCommand('copy')` for older browsers

## Files to Modify

- `/home/user/projects/feedbacks/index.html` — complete HTML/CSS/JS rewrite of the UI layer. Capture logic (captureFrame, captureScreenshot, startChunkRecording, rotateChunk, transcribeChunk, buildZip, saveToServer, buildPlayerHtml, buildMarkdown) stays the same.

## What Stays the Same

All capture/recording/transcription logic is unchanged:
- `captureFrame()` — VideoFrame + ImageCapture + drawImage fallback
- `captureScreenshot()` — async, with dedup, black frame detection
- `startChunkRecording()` / `rotateChunk()` / `transcribeChunk()` — audio pipeline
- `buildMarkdown()` / `buildZip()` / `saveToServer()` / `buildPlayerHtml()` — output generation
- `server.py` — no changes needed
- Auto-capture interval (1s) + audio chunk rotation (10s)

## Verification

1. Start server: `python3 server.py`
2. Open in browser — should see setup screen with mic level meter
3. Start session — header compresses, timeline appears, status strip shows green pills
4. Share a tab, talk for 30s — timeline populates with IMG + STT entries
5. Stop — completion screen shows path with copy button
6. Click copy — verify clipboard has the path
7. Check `debug.log` in saved session for correct timestamps
