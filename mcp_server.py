#!/usr/bin/env python3
"""Feedbacks MCP server — bridges live capture data into Claude Code sessions.

Exposes tools for Claude to check capture status and poll for new
screenshots/transcripts from an active feedbacks recording session.

The server communicates with the feedbacks HTTP server (server.py) via
its /live-session endpoint. Screenshots are stored as files on disk;
transcripts are returned inline.

Output mirrors the session.md timeline structure: screenshots and transcripts
are grouped into speech spans (speech vs silence intervals), so Claude sees
the same correlated view as the final saved session.

Install:
    claude mcp add feedbacks -- python3 /path/to/feedbacks/mcp_server.py
"""

import json
import os
import urllib.request
from pathlib import Path
from mcp.server.fastmcp import FastMCP

FEEDBACKS_URL = "http://127.0.0.1:8080"
FEEDBACKS_HOME = Path(__file__).resolve().parent
OUTPUT_DIR = Path(os.environ.get("FEEDBACKS_OUTPUT_DIR", str(FEEDBACKS_HOME / "sessions")))

mcp = FastMCP(
    "feedbacks",
    instructions=(
        "Screen+voice capture tool. The feedbacks app captures screenshots and whisper "
        "transcripts during user sessions.\n\n"
        "SAVED SESSIONS: Use feedbacks_sessions() to list all past sessions with dates, "
        "durations, and AI summaries. Use feedbacks_session(name) to get a specific session's "
        "full timeline — screenshots as file paths (read with Read tool), transcripts inline, "
        "grouped by speech spans. This is the same data shown in the web UI.\n\n"
        "LIVE CAPTURE: Use feedbacks_status() to check for an active recording, then "
        "feedbacks_poll(since=0) for the live timeline. Pass latestSeqNum as since for "
        "incremental updates. Use during /review or any task where the user is narrating "
        "what they see on screen."
    ),
)


def _get_live_session(since=0, session_id=None):
    """Fetch live session data from the feedbacks HTTP server."""
    url = f"{FEEDBACKS_URL}/live-session?since={since}"
    if session_id:
        url += f"&session={session_id}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e), "active": False, "events": [], "latestSeqNum": 0}


def _fmt_time(seconds):
    """Format seconds as M:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def _build_timeline(events):
    """Group events into speech-span-based timeline segments.

    Mirrors the session.md structure: screenshots and transcripts are grouped
    into speech intervals, with context frames shown for silence periods.
    """
    screenshots = []
    transcripts = []
    speech_spans = []  # completed spans with start+end
    open_speech_start = None  # track unclosed speech_start

    for e in events:
        t = e.get("type")
        if t == "screenshot":
            screenshots.append(e)
        elif t == "transcript":
            transcripts.append(e)
        elif t == "speech_start":
            open_speech_start = e.get("startTime", e.get("offsetTime", 0))
        elif t == "speech_end":
            speech_spans.append({
                "start": e.get("startTime", e.get("offsetTime", 0)),
                "end": e.get("endTime", e.get("offsetTime", 0)),
            })
            open_speech_start = None  # closed

    # Synthesize a closing span if speech was still active (capture ended mid-speech)
    if open_speech_start is not None:
        max_event_time = max(
            (e.get("offsetTime", 0) for e in events),
            default=open_speech_start + 1,
        )
        speech_spans.append({
            "start": open_speech_start,
            "end": max(max_event_time, open_speech_start + 1),
        })

    if not screenshots and not transcripts:
        return []

    # If we have speech spans, group by them (same logic as buildMarkdown)
    if speech_spans:
        segments = []
        max_time = max(
            (s.get("offsetTime", 0) for s in screenshots),
            default=0,
        )
        max_time = max(max_time, max((sp["end"] for sp in speech_spans), default=0))

        # Build intervals: silence, speech, silence, speech, ...
        intervals = []
        cursor = 0.0
        for span in sorted(speech_spans, key=lambda s: s["start"]):
            if span["start"] > cursor + 0.5:
                intervals.append({"type": "context", "start": cursor, "end": span["start"]})
            intervals.append({"type": "speech", "start": span["start"], "end": span["end"]})
            cursor = span["end"]
        if cursor < max_time:
            intervals.append({"type": "context", "start": cursor, "end": max_time + 1})

        for interval in intervals:
            # Screenshots in this interval
            interval_shots = [
                s for s in screenshots
                if interval["start"] - 0.5 <= s.get("offsetTime", 0) < interval["end"] + 0.5
            ]
            # Transcripts in this interval
            interval_texts = [
                t for t in transcripts
                if interval["start"] - 1 <= t.get("startTime", t.get("offsetTime", 0)) <= interval["end"] + 1
            ]

            segments.append({
                "type": interval["type"],
                "start": interval["start"],
                "end": interval["end"],
                "screenshots": interval_shots,
                "transcripts": interval_texts,
            })
        return segments

    # Fallback: no speech spans yet — assign transcripts to nearest screenshot by time
    segments = []
    for shot in screenshots:
        shot_time = shot.get("offsetTime", 0)
        nearby_text = [
            t for t in transcripts
            if abs(t.get("startTime", t.get("offsetTime", 0)) - shot_time) < 5
        ]
        segments.append({
            "type": "speech" if nearby_text else "context",
            "start": shot_time,
            "end": shot_time + 1,
            "screenshots": [shot],
            "transcripts": nearby_text,
        })
    # Any orphan transcripts not near a screenshot
    assigned_times = set()
    for seg in segments:
        for t in seg["transcripts"]:
            assigned_times.add(id(t))
    orphans = [t for t in transcripts if id(t) not in assigned_times]
    if orphans:
        for t in orphans:
            segments.append({
                "type": "speech",
                "start": t.get("startTime", t.get("offsetTime", 0)),
                "end": t.get("endTime", t.get("offsetTime", 0)),
                "screenshots": [],
                "transcripts": [t],
            })
    segments.sort(key=lambda s: s["start"])
    return segments


def _format_timeline(segments, session_id):
    """Format timeline segments as markdown matching session.md structure."""
    lines = []

    for seg in segments:
        time_range = f"{_fmt_time(seg['start'])} – {_fmt_time(seg['end'])}"

        if seg["type"] == "speech":
            lines.append(f"## {time_range}")
            lines.append("")
            for shot in seg["screenshots"]:
                path = shot.get("imagePath", "")
                lines.append(f"![Screenshot]({path})")
                lines.append("")
            for t in seg["transcripts"]:
                text = t.get("text", "").strip()
                if text:
                    lines.append(f"> {text}")
                    lines.append("")
        else:
            # Context (silence) — show one representative screenshot
            if seg["screenshots"]:
                mid = len(seg["screenshots"]) // 2
                shot = seg["screenshots"][mid]
                path = shot.get("imagePath", "")
                lines.append(f"## {time_range} [context]")
                lines.append("")
                lines.append(f"![Screenshot]({path})")
                lines.append("")
                if len(seg["screenshots"]) > 1:
                    lines.append(f"<!-- {len(seg['screenshots']) - 1} similar frames hidden -->")
                    lines.append("")

    return "\n".join(lines)


def _parse_session_md(md_path):
    """Parse session.md into timeline segments — same logic as server.py parse_session_md."""
    import re
    segments = []
    current = None
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return segments

    for line in text.splitlines():
        line_stripped = line.strip()

        m = re.match(r'^##\s+(\d+:\d+)(?:\s*[-–]\s*(\d+:\d+))?(?:\s*\[context\])?\s*$', line_stripped)
        if m:
            if current is not None:
                segments.append(current)
            is_context = '[context]' in line_stripped
            current = {"time": m.group(1), "timeEnd": m.group(2), "image": None, "marker": None, "transcript": [], "context": is_context}
            continue

        if current is None:
            continue

        m = re.match(r'^!\[.*?\]\(\./images/([\w.-]+)\)$', line_stripped)
        if m:
            current["image"] = m.group(1)
            continue

        m = re.match(r'^\*\*\[Marker\s+(\d+)\s*[—–-]\s*(.*?)\]\*\*$', line_stripped)
        if m:
            current["marker"] = {"number": int(m.group(1)), "description": m.group(2)}
            continue

        if line_stripped.startswith('> '):
            txt = line_stripped[2:].strip()
            if txt and txt not in ('(no speech detected)', '[pause]'):
                current["transcript"].append(txt)

    if current is not None:
        segments.append(current)

    for seg in segments:
        seg["transcript"] = " ".join(seg["transcript"]) if seg["transcript"] else None

    return segments


def _load_session(session_dir):
    """Load a saved session's metadata, summary, and timeline from disk."""
    entry = {"name": session_dir.name, "path": str(session_dir.resolve())}

    meta_file = session_dir / "meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            entry.update(meta)
        except Exception:
            pass

    summary_file = session_dir / "summary.json"
    if summary_file.exists():
        try:
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            entry["heroImage"] = summary.get("heroImage", "001.png")
            entry["summary"] = summary.get("summary", "")
            entry["generatedAt"] = summary.get("generatedAt")
            if summary.get("error"):
                entry["summaryError"] = summary["error"]
            entry["status"] = "done"
        except Exception:
            entry["status"] = "summarizing"
    elif meta_file.exists():
        entry["status"] = "summarizing"
    else:
        entry["status"] = "pending"

    return entry


@mcp.tool()
def feedbacks_sessions() -> str:
    """List all saved feedbacks sessions with metadata and AI summaries.

    Returns a formatted list of all past capture sessions, newest first.
    Each entry includes: session name, date/time, duration, image count,
    transcript count, ticket ID (if any), AI summary, and status.

    This is the same data shown in the feedbacks web UI session list.
    """
    sessions = []
    for d in sorted(OUTPUT_DIR.glob("feedbacks-*"), reverse=True):
        if not d.is_dir():
            continue
        sessions.append(_load_session(d))

    if not sessions:
        return f"No saved sessions found in {OUTPUT_DIR}"

    lines = [f"# Feedbacks Sessions ({len(sessions)} total)\n"]
    lines.append(f"Sessions directory: {OUTPUT_DIR}\n")

    for s in sessions:
        name = s.get("name", "?")
        start = s.get("startTime", "")
        duration = s.get("duration", "?")
        images = s.get("imageCount", 0)
        stt = s.get("sttCount", 0)
        ticket = s.get("ticketId", "")
        status = s.get("status", "?")
        summary = s.get("summary", "")

        lines.append(f"## {name}")
        lines.append(f"- **Date:** {start}")
        lines.append(f"- **Duration:** {duration}")
        lines.append(f"- **Screenshots:** {images} | **Transcripts:** {stt}")
        if ticket:
            lines.append(f"- **Ticket:** {ticket}")
        lines.append(f"- **Status:** {status}")
        if summary:
            lines.append(f"- **Summary:** {summary}")
        lines.append("")

    lines.append("Use `feedbacks_session(name)` to get the full timeline for a specific session.")
    return "\n".join(lines)


@mcp.tool()
def feedbacks_session(name: str) -> str:
    """Get a saved session's full timeline with screenshots and transcripts.

    Returns the session's metadata, AI summary, and complete timeline
    in markdown format matching session.md structure. Screenshot file paths
    are absolute — use the Read tool to view them.

    Args:
        name: Session directory name (e.g. "feedbacks-2026-04-03-00-20-35").
              Get this from feedbacks_sessions().
    """
    session_dir = OUTPUT_DIR / name
    if not session_dir.is_dir():
        # Try fuzzy match
        matches = sorted(OUTPUT_DIR.glob(f"*{name}*"))
        if matches:
            session_dir = matches[-1]
        else:
            return f"Session not found: {name}\nAvailable sessions in {OUTPUT_DIR}:\n" + "\n".join(
                d.name for d in sorted(OUTPUT_DIR.glob("feedbacks-*"), reverse=True)[:10]
            )

    entry = _load_session(session_dir)
    images_dir = session_dir / "images"

    # Header
    lines = [f"# Session: {entry['name']}"]
    lines.append(f"- **Date:** {entry.get('startTime', '?')}")
    lines.append(f"- **Duration:** {entry.get('duration', '?')}")
    lines.append(f"- **Screenshots:** {entry.get('imageCount', 0)} | **Transcripts:** {entry.get('sttCount', 0)}")
    if entry.get("ticketId"):
        lines.append(f"- **Ticket:** {entry['ticketId']}")
    lines.append(f"- **Status:** {entry.get('status', '?')}")
    if entry.get("summary"):
        lines.append(f"- **AI Summary:** {entry['summary']}")
    if entry.get("heroImage"):
        hero_path = images_dir / entry["heroImage"]
        lines.append(f"- **Hero image:** {hero_path}")
    lines.append(f"- **Session dir:** {session_dir.resolve()}")
    lines.append("")

    # Timeline
    session_md = session_dir / "session.md"
    if session_md.exists():
        segments = _parse_session_md(session_md)
        if segments:
            lines.append("---\n")
            lines.append("## Timeline\n")
            for seg in segments:
                time_str = seg["time"]
                if seg["timeEnd"]:
                    time_str += f" – {seg['timeEnd']}"
                if seg["context"]:
                    time_str += " [context]"

                lines.append(f"### {time_str}")
                lines.append("")

                if seg["image"]:
                    img_path = images_dir / seg["image"]
                    lines.append(f"![Screenshot]({img_path})")
                    lines.append("")

                if seg["marker"]:
                    m = seg["marker"]
                    lines.append(f"**[Marker {m['number']} — {m['description']}]**")
                    lines.append("")

                if seg["transcript"]:
                    lines.append(f"> {seg['transcript']}")
                    lines.append("")
        else:
            lines.append("(No timeline segments parsed)")
    else:
        lines.append("(session.md not found)")

    return "\n".join(lines)


@mcp.tool()
def feedbacks_status() -> str:
    """Check if a feedbacks capture session is currently active.

    Returns session info (ID, start time, event count) or indicates no active capture.
    Use this as a lightweight check before polling for events.
    """
    data = _get_live_session(since=999999999)  # High since = no events returned, just metadata

    if data.get("error"):
        return f"Feedbacks server not reachable: {data['error']}\nMake sure server.py is running (python3 server.py in ~/projects/feedbacks)"

    if not data.get("sessionId"):
        return "No active capture session. Start a capture in the feedbacks browser UI (http://localhost:8080)."

    status = "ACTIVE — recording in progress" if data.get("active") else "ENDED — capture finished"
    return (
        f"Session: {data['sessionId']}\n"
        f"Status: {status}\n"
        f"Started: {data.get('startTime', 'unknown')}\n"
        f"Latest sequence number: {data.get('latestSeqNum', 0)}\n"
        f"\nThis session will save to: sessions/{data['sessionId']}/\n"
        f"Use feedbacks_poll() to fetch the live timeline."
    )


@mcp.tool()
def feedbacks_poll(since: int = 0, session_id: str | None = None) -> str:
    """Fetch the live capture timeline, grouped by speech spans.

    Returns a markdown-formatted timeline matching the session.md structure:
    screenshots and transcripts grouped into speech intervals, with context
    frames shown for silence. Screenshot paths are absolute file paths that
    can be read with the Read tool.

    Args:
        since: Only return events with seqNum > this value. Pass 0 for the full
               timeline, or pass the latestSeqNum from a previous poll for
               incremental updates. NOTE: when using since > 0, only new events
               are returned — for the full grouped timeline, use since=0.
        session_id: Optional specific session ID. If omitted, uses the most recent session.

    Returns:
        Markdown timeline with screenshot paths and transcripts grouped by speech spans.
        Pass the returned latestSeqNum as `since` in your next call.
    """
    data = _get_live_session(since=since, session_id=session_id)

    if data.get("error"):
        return f"Feedbacks server not reachable: {data['error']}"

    if not data.get("sessionId"):
        return "No capture session found."

    events = data.get("events", [])
    active = data.get("active", False)
    latest_seq = data.get("latestSeqNum", 0)
    sid = data["sessionId"]
    status_str = "Recording..." if active else "Capture ended."

    if not events:
        return (
            f"Session: {sid} | {status_str}\n"
            f"No new events since seq {since}.\n"
            f"latestSeqNum: {latest_seq}"
        )

    # Build timeline-grouped output
    segments = _build_timeline(events)
    timeline_md = _format_timeline(segments, sid)

    # Count stats
    n_screenshots = sum(len(s["screenshots"]) for s in segments)
    n_transcripts = sum(len(s["transcripts"]) for s in segments)
    n_speech = sum(1 for s in segments if s["type"] == "speech")
    n_context = sum(1 for s in segments if s["type"] == "context")

    header = (
        f"# Live Capture — {sid}\n"
        f"Status: {status_str}\n"
        f"Events: {n_screenshots} screenshots, {n_transcripts} transcripts, "
        f"{n_speech} speech spans, {n_context} context frames\n"
        f"latestSeqNum: {latest_seq}\n"
        f"\n---\n\n"
    )

    footer = ""
    if active:
        footer = "\n---\nCapture is still active. Poll again with `feedbacks_poll(since={})` for updates.".format(latest_seq)
    else:
        footer = f"\n---\nCapture ended. Final session will be saved to: sessions/{sid}/"

    return header + timeline_md + footer


if __name__ == "__main__":
    mcp.run(transport="stdio")
