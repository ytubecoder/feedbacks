# Session Log

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
