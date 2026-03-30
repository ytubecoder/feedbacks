# Feedbacks UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the feedbacks capture UI into a clean, three-state (Setup → Recording → Done) timeline-centric interface.

**Architecture:** Single-file app (`index.html`) rewrite. All HTML and CSS replaced. JS split into: preserved capture logic (unchanged) + new UI state machine + new mic level meter + new timeline renderer. No new files.

**Tech Stack:** Vanilla HTML/CSS/JS, AudioContext API for mic level, existing JSZip CDN.

---

## File Structure

All changes in one file:

- **Modify:** `/home/user/projects/feedbacks/index.html`
  - **CSS** (lines 8-249): Complete rewrite — new styles for three states
  - **HTML** (lines 250-325): Complete rewrite — setup, recording, done views
  - **JS — UI layer** (new): State machine, mic level meter, timeline renderer, clipboard copy
  - **JS — Capture logic** (lines 456-1162): PRESERVED UNCHANGED — `captureFrame`, `captureScreenshot`, `startChunkRecording`, `rotateChunk`, `transcribeChunk`, `buildMarkdown`, `buildZip`, `saveToServer`, `buildPlayerHtml`, `drawMarker`, `drawSelectionBox`
  - **JS — Helpers** (lines 1401-1517): Mostly preserved — `formatTime`, `getSupportedMimeType`, `cleanup` updated

**Functions to REMOVE** (replaced by new UI):
- `initTicketId`, `showTicketBadge`, `clearTicketId` — simplified inline
- `mapToVideoCoords` + mouse event handlers — preview removed
- `addTimelineEntry`, `clearTimeline` — replaced by new timeline renderer
- `updateDiagOverlay` + keyboard shortcut — replaced by status strip
- `setStatus` — replaced by state machine
- `updateTranscribeProgress` — replaced by status strip

**Functions to ADD:**
- `switchState(state)` — manages Setup/Recording/Done views
- `initMicMeter(stream)` / `stopMicMeter()` — AudioContext level meter
- `renderMicLevel()` — rAF loop drawing bars
- `insertTimelineEntry(type, timestamp, content, imgSrc, chunkId)` — sorted insertion
- `insertSTTPlaceholder(chunkId, timestamp)` — pending transcript entry
- `replaceSTTPlaceholder(chunkId, text, timestamp)` — fill in transcript
- `updateStatusStrip()` — refresh pill values
- `copyPath()` — clipboard copy with feedback
- `resetToSetup()` — clean restart
- `initMicPreview()` — request mic on page load for level meter

---

### Task 1: Rewrite HTML structure with three-state layout

**Files:**
- Modify: `/home/user/projects/feedbacks/index.html:1-325` (HTML + CSS section)

- [ ] **Step 1: Replace the entire `<style>` block and `<body>` HTML**

Replace lines 8-325 (everything from `<style>` to `<script>`) with the new three-state layout. The HTML has three top-level view containers (`#setupView`, `#recordingView`, `#doneView`) that get shown/hidden by the state machine.

Key CSS classes:
- `.view` / `.view.active` — state visibility
- `.setup` — centered layout with readiness checks
- `.rec-header` / `.status-strip` / `.timeline` / `.rec-footer` — recording layout
- `.done` — centered completion with path + actions
- `.pill` / `.pill-ok` / `.pill-info` / `.pill-off` / `.pill-muted` — status strip pills
- `.tl-entry` / `.tl-badge-img` / `.tl-badge-stt` — timeline entries
- `.mic-bars` / `.mic-bars.large` / `.mic-bars.mini` — mic level bars
- `.readiness-item` / `.dot.ok` / `.dot.off` — setup checklist
- `.done-path` / `.copy-btn` — clipboard copy button

Key HTML elements:
- `#setupView` — with `#sttDot`, `#sttValue`, `#micDot`, `#micBarsSetup`, `#apiKeyRow`, `#apiKey`, `#ticketId`, `#startBtn`
- `#recordingView` — with `.rec-header` (stop btn, `#recTime`, `#micBarsRec`, `#statImg`, `#statStt`), `#statusStrip` (pills: `#pillStt`, `#pillMic`, `#pillCapture`, `#pillImgCount`, `#pillSttCount`, `#pillDedup`), `#timeline`, `.rec-footer` with `<details>` containing `#diagSummary` and `#log`
- `#doneView` — with `#doneSummary`, `#donePathText`, `#copyBtn`
- `#captureVideo` — hidden video element for getDisplayMedia (replaces old `#preview`)

Note: The `#log` element is now inside the diagnostics `<details>` in the recording footer. The `log()` function still targets `$('log')` by ID — no change needed.

See design spec at `docs/superpowers/specs/2026-03-31-ui-redesign-design.md` and the mockup at `.superpowers/brainstorm/*/content/layout-v2.html` for the exact visual design.

- [ ] **Step 2: Verify the HTML is well-formed**

Open browser dev tools, check for HTML parse errors.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: rewrite HTML/CSS for three-state timeline-centric UI"
```

---

### Task 2: Add UI state machine, mic level meter, and timeline renderer

**Files:**
- Modify: `/home/user/projects/feedbacks/index.html` — JS section, add new functions after the `$` helper

- [ ] **Step 1: Add state machine, mic meter, timeline renderer, status strip updater, clipboard copy, and reset function**

Insert these functions right after the `const $ = id => document.getElementById(id);` line. These replace the removed UI functions.

Key implementation details:

**`switchState(state)`** — toggles `.active` class on the three view containers.

**`initMicMeter(stream)`** — creates `AudioContext` + `AnalyserNode` from mic stream, starts rAF loop.

**`renderMicLevel()`** — reads `getByteFrequencyData()`, maps to bar heights. Updates both `#micBarsSetup` (5 bars, 14px tall) and `#micBarsRec` (3 bars, 10px tall). Bars get `.active` class when signal > 10.

**`initMicPreview()`** — requests mic permission on page load, initializes meter, enables start button. Stores stream in `window._previewMicStream` for reuse in `startSession()`.

**`insertTimelineEntry(type, timestamp, content, imgSrc, chunkId)`** — creates a `.tl-entry` div with timestamp, badge, and content. Inserts in sorted order by `data-timestamp`. Auto-scrolls if user is near bottom (within 80px).

**`insertSTTPlaceholder(chunkId, timestamp)`** — calls `insertTimelineEntry` with type `'stt-pending'`, content `'transcribing...'`, and `data-chunk-id="chunk-N"`.

**`replaceSTTPlaceholder(chunkId, text, timestamp)`** — finds placeholder by `data-chunk-id`, replaces content with actual text, updates badge class. Falls back to normal insertion if placeholder not found.

**`updateStatusStrip()`** — refreshes all pill values: STT status (local/cloud/off), capture resolution, img count, stt progress, dedup count. Also updates `#diagSummary` text and header stats (`#statImg`, `#statStt`).

**`copyPath()`** — uses `navigator.clipboard.writeText()`, changes button text to "Copied!" for 2 seconds. Has `document.execCommand('copy')` fallback.

**`resetToSetup()`** — calls `cleanup()`, `switchState('setup')`, `initMicPreview()`.

Add state variable: `let dedupCount = 0;`
Add state variable: `let statusStripIntervalId = null;`
Add state variable: `let savedPath = '';`

- [ ] **Step 2: Verify JS syntax**

Run syntax check — expected: OK

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add UI state machine, mic level meter, timeline renderer"
```

---

### Task 3: Wire capture logic to new UI

**Files:**
- Modify: `/home/user/projects/feedbacks/index.html` — update `startSession()`, `stopSession()`, `captureScreenshot()`, `rotateChunk()`, `transcribeChunk()`, `checkWhisper()`, `cleanup()`, page init

- [ ] **Step 1: Update `startSession()`**

Key changes:
- Use `$('captureVideo')` instead of `$('preview')` for the video element
- Reuse `window._previewMicStream` if active, otherwise request new mic
- Call `switchState('recording')` instead of toggling old buttons/placeholder
- Start `statusStripIntervalId = setInterval(updateStatusStrip, 1000)`
- Reset `dedupCount = 0`
- Remove all references to: `$('preview')`, `$('placeholder')`, `$('clickHint')`, `$('captureCount')`, `$('transcribeProgress')`, `$('downloadBtn')`, `$('startBtn')`, `$('stopBtn')`, `setStatus()`

The `loadedmetadata` handler and `screenshotIntervalId` stay the same but reference `$('captureVideo')` instead of `$('preview')`.

- [ ] **Step 2: Update `stopSession()`**

Key changes:
- After saving, set `savedPath` and switch to done view:
```javascript
savedPath = savedResult || '';
$('doneSummary').textContent = `${screenshots.length} screenshots, ${transcribedCount} transcript chunks, ${formatTime((Date.now() - sessionStartTime) / 1000)} duration`;
$('donePathText').textContent = savedPath || 'Server save failed — use Download ZIP';
switchState('done');
```
- `clearInterval(statusStripIntervalId)` + final `updateStatusStrip()`
- Remove all references to old UI elements

- [ ] **Step 3: Update `captureScreenshot()`**

Replace old timeline/test panel updates with:
```javascript
insertTimelineEntry('img', elapsed, null, dataUrl);
updateStatusStrip();
```

In the dedup skip path, increment `dedupCount++` before returning.

Remove: `$('testImg')`, `$('testImgStats')`, `$('testBlackCheck')`, `$('captureCount')`, old `addTimelineEntry()` calls.

- [ ] **Step 4: Update `rotateChunk()`**

After `chunkCount++`, add:
```javascript
insertSTTPlaceholder(chunkCount, chunkStartTime);
```

Remove: `$('testAudioStats')` reference.

- [ ] **Step 5: Update `transcribeChunk()`**

In success path, replace test panel updates with:
```javascript
const transcriptText = segments.map(s => s.text).join(' ').trim();
replaceSTTPlaceholder(chunkNum, transcriptText, offsetTime);
updateStatusStrip();
```

Remove: `$('testTranscript')`, `$('testPlayerStats')` references.

- [ ] **Step 6: Update `checkWhisper()`**

Replace old `$('whisperDot')` / `$('whisperLabel')` / `$('apiKey').style.opacity` with:
```javascript
const hasKey = $('apiKey')?.value.trim().length > 0;
$('sttDot').className = 'dot ' + (whisperLocal ? 'ok' : (hasKey ? 'ok' : 'off'));
$('sttValue').textContent = whisperLocal ? 'Local (small.en)' : (hasKey ? 'Cloud (OpenAI)' : 'No STT');
$('sttValue').style.color = whisperLocal ? '#4ade80' : (hasKey ? '#58a6ff' : '#f87171');
if (!whisperLocal) $('apiKeyRow').style.display = 'flex';
```

- [ ] **Step 7: Update duration timer in `startSession()`**

Change `$('duration')` to `$('recTime')`:
```javascript
durationIntervalId = setInterval(() => {
  const elapsed = (Date.now() - sessionStartTime) / 1000;
  $('recTime').textContent = formatTime(elapsed);
}, 500);
```

- [ ] **Step 8: Update `cleanup()`**

```javascript
function cleanup() {
  if (screenStream) screenStream.getTracks().forEach(t => t.stop());
  if (micStreamRef) micStreamRef.getTracks().forEach(t => t.stop());
  stopMicMeter();
  clearInterval(durationIntervalId);
  clearInterval(chunkRotationId);
  clearInterval(screenshotIntervalId);
  clearInterval(statusStripIntervalId);
  isRecording = false;
}
```

- [ ] **Step 9: Update page initialization**

Replace all old init code (bottom of script) with:
```javascript
checkWhisper();
whisperCheckId = setInterval(checkWhisper, 5000);
initMicPreview();

const savedApiKey = localStorage.getItem('feedbacks_api_key');
if (savedApiKey && $('apiKey')) $('apiKey').value = savedApiKey;
if ($('apiKey')) $('apiKey').addEventListener('change', () => {
  localStorage.setItem('feedbacks_api_key', $('apiKey').value);
});

const savedTicket = localStorage.getItem('feedbacks_ticket_id');
if (savedTicket && $('ticketId')) $('ticketId').value = savedTicket;
if ($('ticketId')) $('ticketId').addEventListener('change', function() {
  if (this.value.trim()) localStorage.setItem('feedbacks_ticket_id', this.value.trim());
  else localStorage.removeItem('feedbacks_ticket_id');
});
```

- [ ] **Step 10: Remove dead code**

Delete entirely:
- `initTicketId`, `showTicketBadge`, `clearTicketId`
- `mapToVideoCoords` + `$('preview').addEventListener('mousedown'...)` + `$('preview').addEventListener('mouseup'...)`
- Old `addTimelineEntry`, `clearTimeline`
- `updateDiagOverlay` + Ctrl+Shift+D keyboard handler
- `setStatus`
- `updateTranscribeProgress`
- `captureInProgress` declaration near mouse handlers (move to state vars if needed)
- `dragStart` variable and related mouse state
- `markerCount` (no more manual markers)

- [ ] **Step 11: Verify syntax and run**

Syntax check, then `python3 server.py` and open browser.

- [ ] **Step 12: Commit**

```bash
git add index.html
git commit -m "feat: wire capture logic to new three-state UI"
```

---

### Task 4: End-to-end verification

**Files:** None (testing only)

- [ ] **Step 1: Verify setup state**

Open `http://localhost:8080`. Expected: Centered layout, readiness checks, mic level meter animating, Start button enabled.

- [ ] **Step 2: Verify recording state**

Start session, share a tab, talk for 30s. Expected: Header with stop/timer/mic, status strip green, timeline with IMG + STT entries, STT placeholders replaced when transcription arrives.

- [ ] **Step 3: Verify done state**

Stop recording. Expected: "Session Saved" with path. Click copy — clipboard has path. Download ZIP works.

- [ ] **Step 4: Verify new session**

Click "New Session". Expected: Returns to setup, mic meter active.

- [ ] **Step 5: Check debug.log**

```bash
ls -lt ~/projects/feedbacks/sessions/ | head -2
cat ~/projects/feedbacks/sessions/feedbacks-*/debug.log | tail -20
```

Expected: Normal logs with correct timestamps.

- [ ] **Step 6: Final commit**

```bash
git add index.html
git commit -m "feat: complete UI redesign — timeline-centric three-state layout"
```
