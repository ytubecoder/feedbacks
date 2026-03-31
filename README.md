# Feedbacks

Point-and-talk feedback capture for AI analysis. Share your screen, narrate what you see, and get structured output for LLM ingestion.

## What is this?

Feedbacks captures your screen and voice simultaneously while you browse a web app. You talk naturally — "this button looks off", "when I scroll here the layout breaks" — and the tool records timestamped screenshots with your cursor position alongside a transcript of what you said.

The output is a directory of images + markdown, designed to be consumed by an LLM agent that can see what you were pointing at and read what you were saying.

## Quick Start

### One command (with Claude Code)

```
/feedbacks
```

First run installs whisper.cpp and downloads a model. Subsequent runs start the capture server. After a session, run `/feedbacks` again to analyze.

### Install the Claude Code skill

```bash
cp -r ~/projects/feedbacks/skills/feedbacks ~/.claude/skills/feedbacks
```

This installs the `/feedbacks` command globally for Claude Code. After install, `/feedbacks` works from any project directory.

### Manual install

**Prerequisites:** Python 3, ffmpeg, CMake, C/C++ compiler, Chrome

```bash
git clone <this-repo>
cd feedbacks

# server.py handles everything — builds whisper.cpp, downloads model, starts servers
python3 server.py
```

Open **http://localhost:8080** in Chrome. Press Ctrl+C to stop.

That's it. `server.py` will:
- Clone and build whisper.cpp if not present
- Download `small.en` model if no model found
- Start whisper-server on :8081
- Start the app server on :8080 with auto-save and transcription proxy

If whisper setup fails, the app still works — enter an OpenAI API key in the UI for cloud transcription.

### Options

```bash
python3 server.py --port 8080 --whisper-port 8081  # custom ports
python3 server.py --no-whisper                       # skip whisper, cloud-only
FEEDBACKS_OUTPUT_DIR=./my-sessions python3 server.py # custom output directory
```

## Usage

1. **New Capture** — click the button (or the dropdown ▾ to set a ticket ID first)
2. **Share your screen** — Chrome's native share dialog opens immediately
3. **Talk and point** — move your cursor to things as you narrate. Screenshots auto-capture every second when the screen changes.
4. **Voice activity detection** — audio chunks are only sent to whisper when you're speaking. Silence is ignored, eliminating hallucinations. The recording row glows green when your voice is detected.
5. **Switch back** to the feedbacks tab and click **Stop**
6. **Copy the path** to clipboard or download the ZIP

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

## Ticket Integration

Feedbacks can optionally link a session to a ticket ID. This is useful when reviewing features tracked in a project management system.

### Setting a ticket ID

**Via URL parameter** (used by `/review` skill):
```
http://localhost:8080/?ticket=B-05
```
The field pre-fills as read-only and shows a "From /review" badge.

**Via the UI:** Type a ticket ID into the "Ticket ID" field. It persists in localStorage across sessions and shows a "Linked" badge.

**Retroactively:** If you forget to set a ticket ID before recording, a prompt appears after stopping: "No ticket linked." Enter the ID there — it updates the download filename.

### Effect on output

When a ticket ID is set:
- `session.md` header includes a `Ticket: B-05` line
- ZIP filename becomes `feedbacks-B-05-2026-03-31T12-07-32.zip` (instead of `feedbacks-2026-...`)
- Player metadata shows the ticket ID

When no ticket ID is set, everything works identically to before.

### Integration with `/review`

The [ticket-takeaway](/review) skill can use feedbacks sessions as structured input when reviewing visual features. The flow:

1. `/review` detects a visual ticket and suggests recording a session
2. You open `http://localhost:8080/?ticket=B-05` and record
3. Download the ZIP and unpack it:
   ```bash
   unzip ~/Downloads/feedbacks-B-05-*.zip -d docs/features/B-05/feedbacks/$(date +%Y%m%d-%H%M%S)/
   ```
4. Next time `/review B-05` runs, it finds the session automatically
5. Each marker+transcript pair becomes a bug candidate you can accept, edit, or skip

This integration is fully optional — both tools work standalone without the other.

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
└─────────────────────┘<──────────────│ whisper-server    │
        │                              │ (auto-started)    │
        │ auto-save + optional ZIP     └──────────────────┘
        ▼
   sessions/feedbacks-{ts}/
   ├── session.md + images/
   ├── player.html + debug.log
        │
        │ /feedbacks skill
        ▼
   LLM agent analysis
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

MIT
