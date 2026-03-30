# Feedbacks

Point-and-talk feedback capture for AI analysis. Share your screen, click on things, say what you think — get structured analysis back from Claude.

## What is this?

Feedbacks is a browser-based tool that lets you give visual + verbal feedback on any application. You share your screen, click or drag to mark areas of interest, and narrate your thoughts out loud. The tool captures annotated screenshots (with numbered markers showing where you clicked) and transcribes your voice in real-time using a local speech-to-text engine.

The output is a lightweight ZIP containing a markdown document with your annotated screenshots and timestamped transcript — ready for AI analysis via the included Claude Code skill.

## Why?

Giving feedback on a UI is hard to do in text. You end up writing paragraphs like "the button in the top-right corner of the settings panel, no the other one, the blue one..." when you could just *point at it and say what you mean*.

This tool captures pointing + speaking together, so an AI can understand exactly what you're referring to when you say "make this red" or "this area needs work."

## Privacy — not creepy, here's why

This tool captures your screen and microphone. That sounds invasive, so here's exactly what happens to your data:

- **Everything runs locally.** The web app runs on `localhost`. Speech-to-text runs on your machine via [whisper.cpp](https://github.com/ggerganov/whisper.cpp). Nothing is sent to any server unless you explicitly choose the OpenAI cloud fallback.
- **Audio is never saved.** Voice is transcribed in 10-second chunks during the session, then discarded. The output ZIP contains only text and screenshots — no audio files.
- **Screenshots stay on your machine.** They go into a ZIP on your local filesystem. You choose when and where to share them.
- **No analytics, no telemetry, no accounts.** The app is a single HTML file with zero tracking.
- **You control the screen share.** The browser's native screen share picker lets you choose exactly which window or tab to share. You can stop sharing at any time.
- **The source is vanilla JS in a single HTML file.** Read it yourself. There's nothing hidden.

If you use the OpenAI Whisper API fallback (optional, for users who don't want to set up local whisper), audio chunks are sent to OpenAI's servers for transcription. This is the only case where data leaves your machine, and it's opt-in.

## Install

### With Claude Code (recommended)

Clone this repo, then run `/feedbacks` from the project directory. The skill auto-detects what to do:

```
/feedbacks          # first run → builds whisper.cpp, downloads model
/feedbacks          # next run → starts the capture app
/feedbacks          # after a session → analyzes your latest capture
```

You can also be explicit:

```
/feedbacks setup
/feedbacks start
/feedbacks analyze
```

To make `/feedbacks` available from any project, copy the skill to your global Claude config:

```bash
cp -r .claude/skills/feedbacks ~/.claude/skills/
```

### Manual setup

**Prerequisites:** Python 3, CMake, C/C++ compiler, curl

```bash
# 1. Clone
git clone https://github.com/anthropics/feedbacks.git
cd feedbacks

# 2. Build whisper.cpp
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp && cmake -B build && cmake --build build -j --config Release && cd ..

# 3. Download a speech-to-text model
sh whisper.cpp/models/download-ggml-model.sh small.en

# 4. Launch (starts whisper + app server automatically)
python3 server.py
```

Open **http://localhost:8080** in Chrome. Press Ctrl+C to stop both servers.

`server.py` auto-detects whisper binary and model, starts it, and provides a WebM→WAV transcription proxy. If whisper.cpp isn't installed, it attempts to clone and build it automatically.

### No-install cloud mode

Open `http://localhost:8080` and enter an OpenAI API key for transcription (~$0.006/min). No whisper.cpp needed — but audio is sent to OpenAI's servers.

## Usage

1. Click **Start Session** — grant screen share + microphone
2. **Switch to the tab/window** you want to give feedback on
3. **Talk and point** — move your cursor to areas of interest as you narrate. Screenshots auto-capture every second when the screen changes (cursor movement counts).
4. Go back to the feedbacks tab and click **Stop**
5. Session auto-saves to disk. **Copy the path** or **Download ZIP**.

### What you get

```
sessions/feedbacks-2026-03-31-12-07-32/
├── session.md          # timestamped transcript with screenshot refs
├── player.html         # self-contained slideshow player
├── debug.log           # capture diagnostics
└── images/
    ├── 001.png         # auto-captured screenshot (cursor visible)
    ├── 002.png
    └── ...
```

Example `session.md`:

```markdown
## 0:12 - 0:25
![Screenshot 2](./images/002.png)

> When I click on settings here, it takes a while to load and the spinner is barely visible...
```

### Analyze with Claude Code

```
/feedbacks
```

Claude reads each annotated screenshot, sees where you clicked, matches your markers to what you were saying ("this" → Marker 3), and provides structured feedback with action items.

## Architecture

```
Browser (index.html)                    server.py (:8080)
┌─────────────────────┐                ┌──────────────────┐
│ getDisplayMedia      │  POST /save   │ Save sessions     │
│ VideoFrame API       │──────────────>│ to disk           │
│ MediaRecorder        │               │                   │
│ Auto-capture (1s)    │  POST /transcr│ WebM→WAV (ffmpeg) │
│ Dedup + timeline UI  │──────────────>│ → whisper (:8081) │
│ JSZip                │  transcript   │                   │
└─────────────────────┘<──────────────│ whisper-server    │
        │                              │ (auto-started)    │
        │ auto-save / ZIP              └──────────────────┘
        ▼
   sessions/feedbacks-{ts}/
   ├── session.md + images/
   ├── player.html
   └── debug.log
        │
        │ /feedbacks skill
        ▼
   Claude Code analysis
```

No database. No accounts. Single HTML file + Python server.

## Model recommendations

| Model | Size | Speed (CPU) | Accuracy |
|-------|------|-------------|----------|
| `tiny.en` | 75MB | Very fast | Good enough for testing |
| `base.en` | 150MB | Fast | Good for testing |
| `small.en` | 500MB | Moderate | **Recommended** — good accuracy |
| `medium.en` | 1.5GB | Slow | High accuracy |

`.en` variants are English-only — faster and smaller than multilingual models.

## License

MIT
