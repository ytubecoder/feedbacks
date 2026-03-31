# Decision 001: Whisper initial_prompt Removed

**Date:** 2026-03-30
**Status:** Decided — prompt removed, VAD enabled instead

## Context

Whisper's `initial_prompt` parameter provides contextual hints that guide transcription style and vocabulary. The theory: feeding recent transcript text as a prompt gives whisper continuity across 10-second audio chunks, improving accuracy for domain-specific terms and reducing chunk-boundary artifacts.

## What we tried

**v1 (initial commit, 2026-03-29):** No prompt at all. Bare whisper transcription with default settings.

**v2 (UI redesign, 2026-03-31):** Added a two-part prompt strategy:
- First chunk: `"Feedback session on a web application. User is describing what they see on screen."`
- Subsequent chunks: `"Feedback session on a web application. Previous: {last 150 chars of transcript}"`

The intent was:
1. Give whisper context about the domain (web app feedback)
2. Improve continuity between 10-second chunks by feeding prior transcript
3. Help whisper resolve ambiguous words using prior context

## What happened

The initial prompt caused **whisper to hallucinate the prompt text as transcript output** when audio was quiet, unclear, or had low speech content. Specifically:

- Silent audio chunks returned: `"User is describing what they see on screen. User is"`
- Quiet segments returned variations of the prompt text mixed with actual speech
- The hallucinated text propagated: once one chunk hallucinated, the `Previous:` context for the NEXT chunk contained the hallucinated text, creating a feedback loop

This is a known whisper behavior — the model treats `initial_prompt` as a style/content prior, and when audio evidence is weak, it falls back to generating text consistent with the prompt rather than admitting silence.

## Decision

**Remove the descriptive initial prompt entirely.** Replace with:

- **First chunk:** Empty prompt (no `prompt` field sent to whisper)
- **Subsequent chunks:** Raw recent transcript text only (no "Feedback session" prefix, no descriptive framing)

This preserves chunk-to-chunk continuity (prior transcript helps whisper stay consistent) without giving it descriptive text to hallucinate.

**Additionally, enable VAD (Voice Activity Detection):**

- `--vad` flag with Silero VAD model — detects whether audio contains actual speech before attempting transcription
- `--suppress-nst` — suppresses non-speech tokens (coughs, breathing, background noise)
- `--no-speech-thold 0.5` — stricter no-speech threshold (default 0.6)

VAD is the proper solution to the hallucination problem — it rejects silent audio at the detection stage rather than trying to transcribe it and hoping the model says "no speech."

## Trade-offs

| Approach | Accuracy on clear speech | Behavior on silence | Continuity |
|----------|------------------------|--------------------|-----------|
| No prompt | Baseline | Returns empty or short noise | No continuity |
| Descriptive prompt (v2) | Slightly better domain terms | Hallucates prompt text | Good continuity but poisoned |
| Prior transcript only (v3, current) | Baseline + context | Returns empty (with VAD) | Good continuity, clean |

The descriptive prompt's accuracy benefit on clear speech was marginal — whisper small.en already handles web/UI vocabulary well. The hallucination cost on quiet audio far outweighed the benefit.

## What to watch for

- If transcription quality regresses on clear speech (unlikely), consider adding back a very short, non-descriptive prompt like `"..."` (whisper interprets ellipsis as "continue previous context")
- The VAD model (`silero-v6.2.0`) may need updating as whisper.cpp evolves
- If chunk boundaries produce more artifacts without the prompt prefix, the prior-transcript-only approach may need the context window increased from 200 to 300 chars

## Update: condition_on_previous_text=False (2026-03-31)

Removed the remaining `prompt` field entirely from whisper requests. Even sending recent transcript text as context was causing hallucination cascades — one bad output seeded the next chunk's prompt, creating repeated nonsense.

Additionally implemented:
- **Hallucination blocklist** — known phrases whisper produces on silence/noise (e.g., "Thank you for watching", "Please subscribe"). Case-insensitive exact match, dropped before storage.
- **Repeated-output detection** — if the same text appears 3+ times within a single chunk, all segments are dropped. Catches stuck-loop hallucinations independently of the blocklist.
- **Client-side VAD** — WebAudio energy-based voice activity detection. Chunks are only recorded and sent to whisper when speech is detected. Combined with server-side Silero VAD, this provides double coverage.

## Files changed

- `index.html` — VAD state machine, speech-driven chunk rotation, hallucination filters, removed prompt field from whisper requests
- `server.py` — whisper-server startup flags (`--vad`, `--suppress-nst`, `--no-speech-thold`), `parse_session_md()` for speech-span format
