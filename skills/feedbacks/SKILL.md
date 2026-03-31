---
name: feedbacks
description: All-in-one skill — setup whisper.cpp, launch the capture app, or analyze a captured session. Works from any project.
user_invocable: true
arguments:
  - name: command
    description: "Optional: 'setup', 'start', 'analyze', or a path to a session. Omit to auto-detect what to do."
    required: false
---

# Feedbacks — Unified Skill

This skill handles everything: first-time setup, launching the capture app, and analyzing sessions.
It works from **any project directory** — the feedbacks tool lives at `/home/user/projects/feedbacks`.

**FEEDBACKS_HOME:** `/home/user/projects/feedbacks`

## Determine what to do

Check `$ARGUMENTS.command`:

- If `setup` → go to **Setup**
- If `start` → go to **Start**
- If `analyze` or a file/directory path → go to **Analyze**
- If omitted → **Auto-detect**:

### Auto-detect logic

1. Check if FEEDBACKS_HOME exists: `ls /home/user/projects/feedbacks/start.sh`
   - If not → tell the user the feedbacks project isn't installed and provide clone instructions
2. Check if `whisper.cpp/build/bin/whisper-server` exists in FEEDBACKS_HOME
   - If not → tell the user: "First time? Running setup." → go to **Setup**
3. Check if whisper-server is already running: `curl -sf http://localhost:8081/health`
   - If not running → go to **Start**
   - If running → go to **Analyze** (app is already up, user probably has a session to review)

---

## Setup

Install whisper.cpp and download a model. Run these commands:

```bash
cd /home/user/projects/feedbacks

# Clone and build whisper.cpp
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
cmake -B build
cmake --build build -j --config Release
cd ..

# Download the base English model
sh whisper.cpp/models/download-ggml-model.sh base.en
```

Run each step, check for errors between steps. If `cmake` or build tools are missing, install them:
```bash
sudo apt update && sudo apt install -y build-essential cmake
```

After setup completes, tell the user:
> Setup complete! Run `/feedbacks` again to start the capture app.

---

## Start

Launch the capture app and whisper server.

1. First, check if ports 8080/8081 are already in use:
   ```bash
   curl -sf http://localhost:8081/health && echo "Whisper already running" || echo "Whisper not running"
   curl -sf http://localhost:8080/ && echo "App already running" || echo "App not running"
   ```
2. **Determine output directory** based on context:
   - If `FEEDBACKS_OUTPUT_DIR` is already set in the environment, use it
   - If launched from a project with a ticket/feature context (e.g., ticket takeaway), set it to:
     `{project_root}/.feedbacks/{ticket-id}/` (e.g., `~/projects/myapp/.feedbacks/FEAT-42/`)
   - If launched from a project without ticket context, set it to:
     `{project_root}/.feedbacks/`
   - If launched standalone (from feedbacks project itself), default to:
     `./sessions/` (the feedbacks project default)
3. If not running, start them:
   ```bash
   FEEDBACKS_OUTPUT_DIR=/path/to/output cd /home/user/projects/feedbacks && ./start.sh whisper.cpp/models/ggml-base.en.bin
   ```
   Run this in the background so the user can continue using Claude Code.
4. Tell the user:
   > Feedbacks is running at **http://localhost:8080**
   > Sessions will auto-save to: `{output_dir}`
   > Open it in Chrome, capture your session, then run `/feedbacks` to analyze it.

**With ticket context:**
If invoked as `/feedbacks start {ticket-ID}`:
- Include `?ticket={ticket-ID}` in the URL: `http://localhost:8080/?ticket={ticket-ID}`
- The ticket ID will be pre-filled in the capture UI and embedded in the session output
- After recording, the ZIP filename will include the ticket ID: `feedbacks-{ticket-ID}-{timestamp}.zip`
- Tell the user:
  > Feedbacks is running at **http://localhost:8080/?ticket={ticket-ID}**
  > Open it in Chrome, capture your session, then run `/feedbacks` to analyze it.

**Saving session for /review integration:**
After downloading the ZIP, if a ticket ID was set, suggest the unpack command:
```bash
unzip ~/Downloads/feedbacks-{ticket-ID}-*.zip -d docs/features/{ticket-ID}/feedbacks/$(date +%Y%m%d-%H%M%S)/
```
Then note: "Next time you run `/review {ticket-ID}`, it will automatically detect and use this session."

---

## Analyze

Ingest and analyze a captured feedback session.

### Finding the session

If a path was provided in `$ARGUMENTS.command`, use it directly. Otherwise:

1. **Check server output directory first** — query the running server for its config:
   ```bash
   curl -sf http://localhost:8080/config
   ```
   If it returns an `outputDir`, use Glob to find the latest `feedbacks-*/session.md` in that directory.
   Sessions are saved as extracted directories (not ZIPs) with this structure:
   ```
   {outputDir}/feedbacks-{timestamp}/
     session.md
     player.html
     images/001.png, 002.png, ...
   ```

2. **Check project-specific `.feedbacks/` directory** — if running from a project context:
   ```bash
   ls -dt {project_root}/.feedbacks/*/session.md 2>/dev/null | head -1
   ```

3. **Fallback to Downloads** — check the user's download directory for ZIP files:
   - Check `~/.claude/memory/feedbacks_download_dir.md` for saved download path
   - Use Glob to find the latest `feedbacks-*.zip`
   - If no memory exists, ask the user for their download directory and save it to memory
   - If the path points to a `.zip` file, extract it:
     ```bash
     unzip -o <path-to-zip> -d /tmp/feedbacks-session
     ```
     Then use the extracted directory.

### Processing the session

**Ticket-aware analysis:**
When reading `session.md`, check for a `Ticket: {ID}` line after the header. If present:
- Note the ticket ID in the analysis output: "This session is linked to ticket {ID}"
- If `docs/features/{ID}/` exists in the current project, suggest archiving: "Consider saving this session to `docs/features/{ID}/feedbacks/` for /review integration"
- If the session is already in `docs/features/{ID}/feedbacks/`, note: "Session already archived for /review"

1. Read `session.md` from the session directory
2. Parse each section — they follow this pattern:
   ```
   ## TIMESTAMP
   ![Screenshot N](./images/NNN.png)
   **[Marker N — user clicked at (x, y)]**
   > Transcript text...
   ```
3. **Coherence pass**: The transcript was progressively transcribed in ~10s chunks. Quickly scan it for:
   - Obvious chunk-boundary artifacts (cut-off sentences between sections)
   - Repeated words at boundaries
   - If you spot issues, silently smooth them in your interpretation — don't flag minor STT artifacts to the user
4. For each section, read the referenced screenshot image using the Read tool (it supports images)
5. **Correlate markers with speech**: When the transcript says "this", "here", "that area" etc., map those deictic references to the numbered markers visible in the screenshot. The marker number tells you exactly what the user was pointing at.
6. **Describe each screenshot** using this structured format. Extract as much context as possible from the image itself — the user's voice only tells half the story.

   For each screenshot, produce:

   ```
   ### Screenshot N · {timestamp}

   **Screen:** {what app/page is shown — e.g., "YouTube video player", "Settings > Billing page", "VS Code editor with server.py open"}
   **URL:** {visible URL from browser address bar, or "not visible" if browser chrome is offscreen}
   **Page title:** {tab title or page heading if readable}
   **Cursor:** {where the cursor is — e.g., "hovering over the Subscribe button", "in the search input field", "not visible"}
   **Marker {N}:** {what the marker is pointing at — e.g., "the 'Save' button in the toolbar", "the third pricing card", "a validation error message below the email field"}
   **Interaction:** {what the user did — click, drag-select, hover. Derive from marker type: red circle = click, red rectangle = drag selection}
   **Visible state:** {anything notable about the current UI state — e.g., "modal is open", "dropdown is expanded", "form has validation errors", "loading spinner visible", "dark mode active"}

   **User said:** "{transcript text}"

   **Interpretation:** {one sentence combining what the user pointed at with what they said — e.g., "User clicked the Save button and noted it doesn't provide visual feedback on success"}
   ```

   **Field rules:**
   - **Screen**: Identify the app from visual cues (favicon, logo, URL, layout). Be specific: "Stripe Dashboard > Customers list" not just "a dashboard".
   - **URL**: Read it literally from the address bar. Include query params if visible. Write "not visible" if the address bar is cropped or offscreen — don't guess.
   - **Cursor**: Describe position relative to UI elements, not pixel coordinates. "On the dropdown arrow next to the user avatar" is useful. "(450, 320)" is not.
   - **Marker**: Describe what the marker is *on top of*, not the marker itself. "The red 'Delete' button" not "a red circle".
   - **Visible state**: Only note what's relevant. A normal page load needs no comment. An error toast, a half-loaded spinner, a disabled button — those matter.
   - **Interpretation**: This is the key output. Fuse the visual evidence (marker position, UI state) with the verbal evidence (transcript). One clear sentence.

   If a screenshot has no marker and no transcript (auto-captured context frame), describe it briefly:
   ```
   ### Screenshot N · {timestamp}
   **Screen:** {app/page}
   **Context frame** — no user interaction. {Brief note of what's visible, e.g., "Page fully loaded, no errors."}
   ```

7. After presenting all sections, provide a **summary analysis**:
   - **Feedback points**: Each issue the user raised, with screenshot number, marker, and one-line description
   - **Navigation path**: The sequence of screens/pages the user visited (reconstructed from URLs and page titles across screenshots)
   - **UI/UX issues**: Problems visible in the screenshots that the user may or may not have mentioned
   - **Suggested action items**: Concrete fixes or investigations, each linked to a specific screenshot

### Important

- Read images with their full path: `<session-dir>/images/NNN.png`
- The transcript comes from Whisper (local or cloud) and may have minor errors — interpret charitably
- Screenshots contain numbered red circle markers or red selection boxes — these show exactly where the user clicked/selected
- Focus on understanding the user's intent by combining the visual markers with the spoken context
