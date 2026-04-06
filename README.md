```
  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
  ░█▀▀░█▀▀░█▀▀░█▀▄░█▀▄░█▀█░█▀▀░█░█░█▀▀ ═══▶═══▶═══▶
  ░█▀▀░█▀▀░█▀▀░█░█░█▀▄░█▀█░█░░░█▀▄░▀▀█  ═══▶═══▶═══▶
  ░▀░░░▀▀▀░▀▀▀░▀▀░░▀▀░░▀░▀░▀▀▀░▀░▀░▀▀▀ ═══▶═══▶═══▶
  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄

           screen · voice · capture for LLMs

             "Show me what you built."
                "Do it just like this."
```

Point-and-talk feedback capture for AI analysis. Share your screen, narrate what you see, and get structured output for LLM ingestion.

## What is this?

Feedbacks captures your screen and voice simultaneously while you browse a web app. You talk naturally — "this button looks off", "when I scroll here the layout breaks" — and the tool records timestamped screenshots with your cursor position alongside a transcript of what you said.

The output is a directory of images + markdown made available over MCP so you get batched transcripts as you go or access to past sessions, all designed to be consumed by an LLM agent that can see what you were pointing at and read what you were saying.

## Quick Start

```bash
git clone https://github.com/ytubecoder/feedbacks.git
cd feedbacks
pip install mcp
cp -r skills/feedbacks ~/.claude/skills/feedbacks
claude mcp add feedbacks -- python3 $(pwd)/mcp_server.py
```

Restart Claude Code. You now have:

- **`/feedbacks`** — skill command to setup whisper, start capture, watch live, or analyze sessions
- **MCP tools** — Claude can browse saved sessions and stream live captures directly

| MCP Tool | Purpose |
|----------|---------|
| `feedbacks_sessions()` | List all saved sessions with dates, durations, AI summaries and ticket ID (if provided) |
| `feedbacks_session(name)` | Get a session's full timeline — screenshots + transcripts |
| `feedbacks_status()` | Check if a live capture is in progress |
| `feedbacks_poll(since)` | Stream live capture events grouped by speech spans |

Then run `/feedbacks` — first run builds whisper.cpp and downloads a model. After that, it starts the capture server at **http://localhost:8080**.

<details>
<summary><b>Manual install (without Claude Code) & Options</b></summary>

**Prerequisites:** Python 3, ffmpeg, CMake, C/C++ compiler, Chrome

```bash
git clone https://github.com/ytubecoder/feedbacks.git
cd feedbacks

# server.py handles everything — builds whisper.cpp, downloads model, starts servers
python3 server.py
```

Open **http://localhost:8080** in Chrome. Press Ctrl+C to stop.

`server.py` will:
- Clone and build whisper.cpp if not present
- Download `small.en` model if no model found
- Start whisper-server on :8081
- Start the app server on :8080 with auto-save and transcription proxy

If whisper setup fails, the app still works — enter an OpenAI API key in the UI for cloud transcription.

**Options:**

```bash
python3 server.py --port 8080 --whisper-port 8081  # custom ports
python3 server.py --no-whisper                       # skip whisper, cloud-only
FEEDBACKS_OUTPUT_DIR=./my-sessions python3 server.py # custom output directory
```

</details>

## Usage

1. **New Capture** — click the button (or the dropdown ▾ to set a ticket ID first)
2. **Share your screen** — Chrome's native share dialog opens immediately
3. **Talk and point** — move your cursor to things as you narrate. Screenshots auto-capture every second when the screen changes.
4. **Voice activity detection** — audio chunks are only sent to whisper when you're speaking. Silence is ignored, eliminating hallucinations. The recording row glows green when your voice is detected.
5. **Transcription activity** — animated indicator shows when audio is being transcribed, with a brief preview of the result
6. **Switch back** to the feedbacks tab and click **Stop**
7. **Copy the path** to clipboard or download the ZIP

Screenshots include your cursor position (baked in by the browser's screen capture API), so when you say "this area here" while pointing, the screenshot shows exactly where you meant.

## Output Format

Each session saves to `sessions/feedbacks-{timestamp}/`:

```
sessions/feedbacks-2026-03-31-12-07-32/
├── session.md      # timestamped markdown — screenshots + transcript
├── player.html     # self-contained slideshow (open in browser)
├── debug.log       # capture diagnostics
└── images/
    ├── 001.png     # auto-captured screenshots (cursor visible)
    ├── 002.png
    └── ...
```

`player.html` includes an interactive timeline with tick marks for each screenshot and purple transcript bars showing where speech occurred — scrub through the session visually.

### session.md format

```markdown
# Feedback Session — 2026-03-31 12:07
Ticket: FEAT-42

## 0:05 - 0:15
![Screenshot 2](./images/002.png)

> The pricing cards look good but this button here seems misaligned with the others.

## 0:15 - 0:22
![Screenshot 5](./images/005.png)

> When I hover over this, the tooltip doesn't appear fast enough.
```

Each section has a timestamp range, a screenshot, and the transcript of what the user was saying during that time window. Images are referenced by relative path.

### For LLM agents

The session output is designed for direct LLM consumption:

- **session.md** is the primary artifact. Read it, then read the referenced images to see what the user was looking at.
- **Timestamps** correlate screenshots to transcript. A screenshot at `0:15` with transcript "this button here" means the cursor in that image is pointing at "this button."
- **Cursor position** is visible in every screenshot. When the user says "this" or "here", look at where the cursor is in the corresponding image.
- **Ticket ID** (if set) appears on the first line after the header. Use it to link feedback to a specific feature or bug.
- **debug.log** contains capture diagnostics — only needed if something seems wrong with the output.
- **player.html** is for human review only. LLM agents should read session.md + images directly.

### Analyze with Claude Code

```
/feedbacks analyze path/to/session
/feedbacks                          # auto-finds latest session
```

The `/feedbacks` skill reads each screenshot, correlates cursor position with speech, and provides structured feedback with action items.

## Feedbacks Integration

Get Feedbacks at [github.com/ytubecoder/feedbacks](https://github.com/ytubecoder/feedbacks/).

### Ticket Linking

Feedbacks can optionally link a session to a ticket ID. This is useful when reviewing features tracked in a project management system.

**Via URL parameter:**
```
http://localhost:8080/?ticket=B-05
```
The field pre-fills as read-only.

**Via the UI:** Type a ticket ID into the "Ticket ID" field. It persists in localStorage across sessions and shows a "Linked" badge.

**Retroactively:** If you forget to set a ticket ID before recording, a prompt appears after stopping: "No ticket linked." Enter the ID there — it updates the download filename.

When a ticket ID is set:
- `session.md` header includes a `Ticket: B-05` line
- ZIP filename becomes `feedbacks-B-05-2026-03-31T12-07-32.zip` (instead of `feedbacks-2026-...`)
- Player metadata shows the ticket ID

When no ticket ID is set, everything works identically to before.

### Recorder Widget (Embed in Other Apps)

Open feedbacks in a compact popup from any app for quick capture sessions:

```js
const popup = window.open(
  'http://localhost:8080/?mode=recorder&ticket=BUG-42',
  'feedbacks-recorder',
  'width=500,height=625'
);

// Get notified when session completes
window.addEventListener('message', (e) => {
  if (e.data?.type === 'feedbacks:session-saved') {
    console.log(e.data.sessionName);  // "feedbacks-BUG-42-2026-..."
    console.log(e.data.ticketId);     // "BUG-42"
    console.log(e.data.duration);     // "1:23"
  }
});
```

The widget shows recording controls, mic level, screenshot/transcript counters, and a live timeline — same capture engine as the full app. The border color reflects state: red while recording, blue while processing/saving, green when done. A transcription activity indicator (animated dots + result preview) shows STT progress in real time. After save, the widget counts down ("Closing in 2...", "Closing in 1...") before auto-closing and sending a `postMessage` with session details.

| Param | Default | Description |
|-------|---------|-------------|
| `mode=recorder` | — | Compact widget UI |
| `ticket=X` | — | Link session to ticket |
| `autostart=1` | `0` | Skip the Start button |
| `autoclose=0` | `1` | Keep window open after save |
| `origin=URL` | `*` | Restrict postMessage origin |

**File-based detection** also works: watch the output directory for new `meta.json` files (written last in the save sequence). Call `GET /config` to get the output directory path.

## Architecture

```
Browser (index.html)                    server.py (:8080)
┌─────────────────────┐                ┌──────────────────┐
│ getDisplayMedia      │  POST /save   │ Save sessions     │
│ VideoFrame API       │──────────────>│ to disk           │
│ MediaRecorder        │               │                   │
│ Auto-capture (1s)    │ POST /transcr │ WebM→WAV (ffmpeg) │
│ Dedup + timeline UI  │──────────────>│ → whisper (:8081) │
│ JSZip                │  transcript   │                   │
│                      │ POST /live-   │ Live state        │
│                      │──push────────>│ (in memory)       │
└─────────────────────┘<──────────────│ whisper-server    │
        │                              │ (auto-started)    │
        │ auto-save + optional ZIP     └────────┬─────────┘
        ▼                                       │ GET /live-session
   sessions/feedbacks-{ts}/               ┌─────┴──────────┐
   ├── session.md + images/               │ mcp_server.py   │
   ├── player.html + debug.log            │ (stdio MCP)     │
        │                                 │                 │
        │ /feedbacks skill                │ feedbacks_poll  │
        ├────────────────────────────────>│ feedbacks_*     │
        ▼                                 └─────┬──────────┘
   LLM agent analysis                          │
        ▲                                       │ MCP tools
        └───────────────────────────────────────┘
```

**Key technical details:**
- `VideoFrame` API captures actual pixels from the screen share stream (canvas.drawImage produces black frames on Chrome)
- Screenshots dedup via horizontal strip comparison — static pages don't generate duplicate images
- Force-capture every 5s ensures minimum coverage even on static pages
- Audio recorded as WebM/Opus, converted to WAV server-side via ffmpeg (whisper.cpp doesn't accept WebM)
- Voice Activity Detection (VAD) drives audio chunk boundaries — speech start/end detected via WebAudio frequency analysis
- Server-side Silero VAD + `--suppress-nst` as additional whisper hallucination prevention

## Transcription Quality

Whisper hallucinations (generating text from silence) are mitigated by a multi-layer stack:

1. **Client-side VAD** — audio chunks only recorded when speech is detected (energy threshold + onset/offset delays)
2. **Server-side Silero VAD** — whisper-server rejects non-speech audio before transcription
3. **No prompt seeding** — previous transcript is not fed back as context (prevents hallucination cascades)
4. **Hallucination blocklist** — known phantom phrases ("Thank you for watching", "Please subscribe", etc.) are dropped
5. **Repeated-output detection** — if the same text appears 3+ times in a chunk, the entire chunk is discarded

When filters activate, a `⚠ Filtered` entry appears in the timeline so you know it happened.

See `docs/decisions/001-whisper-initial-prompt.md` for the full rationale.

## Whisper Models

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny.en` | 75MB | Very fast | Testing only |
| `base.en` | 150MB | Fast | Acceptable |
| **`small.en`** | **500MB** | **Moderate** | **Recommended** |
| `medium.en` | 1.5GB | Slow | High accuracy |

`server.py` prefers `small.en` if available. Download others with:
```bash
sh whisper.cpp/models/download-ggml-model.sh <model-name>
```

## Privacy

- Everything runs locally. No data leaves your machine unless you opt into OpenAI cloud transcription.
- Audio is transcribed in 10-second chunks then discarded. No audio files in the output.
- Screenshots stay on your local filesystem. You choose when to share them.
- No analytics, telemetry, or accounts.

## License

Copyright (c) 2026 ytubecoder. All rights reserved. Free for personal and non-commercial use. Commercial use requires a separate license — see [LICENSE](LICENSE) for details.
