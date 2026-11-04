"""Build a corrected SRT from the narration segment timings (no ASR needed).

Reads artifacts/video/voice/timings.json (start_ms + measured duration per
segment) and the segment texts from scripts/voiceover.py, then writes
artifacts/video/fen-demo.srt.

Layout rules: at most two lines per cue, at most 46 characters per line; a
long segment is split into several cues whose durations are proportional to
their character counts, so captions keep pace with the voice.

YouTube's auto-captions mishear two words ("provenance" -> "provenence",
"human-governed" -> "humaned"); upload this file to replace them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.voiceover import SEGMENTS  # noqa: E402

MAX_CHARS = 46


def wrap_lines(text: str) -> list[str]:
    """Greedy word wrap to <= MAX_CHARS per line."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > MAX_CHARS and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def pages(text: str) -> list[list[str]]:
    """Group wrapped lines into pages of at most two lines."""
    lines = wrap_lines(text)
    return [lines[i:i + 2] for i in range(0, len(lines), 2)]


def stamp(ms: int) -> str:
    ms = max(0, ms)
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def main() -> int:
    timings = json.loads(
        (ROOT / "artifacts/video/voice/timings.json").read_text(encoding="utf-8")
    )
    durations = {item["index"]: item["duration_ms"] for item in timings}

    cues: list[tuple[int, int, list[str]]] = []
    for index, (start_ms, _window_ms, text) in enumerate(SEGMENTS, start=1):
        duration = durations.get(index, 0)
        group = pages(text)
        weights = [sum(len(line) for line in page) for page in group]
        total_weight = sum(weights) or 1
        cursor = start_ms
        for page, weight in zip(group, weights):
            share = int(duration * weight / total_weight)
            cues.append((cursor, cursor + share, page))
            cursor += share
        # small tail on the last page of the segment
        if cues:
            s, e, lines = cues[-1]
            cues[-1] = (s, e + 220, lines)

    # keep cues from overlapping the next segment
    for i in range(len(cues) - 1):
        start, end, lines = cues[i]
        cues[i] = (start, min(end, cues[i + 1][0] - 40), lines)

    out: list[str] = []
    number = 0
    for start, end, lines in cues:
        if end <= start:
            continue
        number += 1
        out.append(str(number))
        out.append(f"{stamp(start)} --> {stamp(end)}")
        out.extend(lines)
        out.append("")

    dest = ROOT / "artifacts/video/fen-demo.srt"
    dest.write_text("\n".join(out), encoding="utf-8")
    longest = max((len(line) for _s, _e, ls in cues for line in ls), default=0)
    print(f"wrote {dest} ({number} cues, longest line {longest} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
