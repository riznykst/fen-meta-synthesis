"""ElevenLabs voiceover: generate 10 segments and mux them onto the demo video.

Environment (repo-root .env or real env vars, values never printed):
    ELEVENLABS_API_KEY   required, starts with sk_
    ELEVENLABS_VOICE_ID  optional — pin a voice; otherwise the single
                         cloned voice is used automatically
    ELEVENLABS_MODEL     optional, default eleven_multilingual_v2

Usage:
    python scripts/voiceover.py --list-voices        # who is available
    python scripts/voiceover.py --generate           # 10 MP3s + timings report
    python scripts/voiceover.py --assemble           # mux onto the video
    python scripts/voiceover.py --generate --assemble

Outputs (artifacts/video/):
    voice/01.mp3 … voice/10.mp3
    voice/timings.json
    fen-demo-voice.mp4   (video + narration, audio starts disabled later)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "video"
VOICE_DIR = OUT / "voice"
VIDEO_IN = OUT / "fen-demo-final-110s.mp4"
VIDEO_OUT = OUT / "fen-demo-voice.mp4"

API = "https://api.elevenlabs.io/v1"

# (start_ms, window_ms, text) — windows come from the frame-sampled timeline.
SEGMENTS = [
    (0, 8000,
     'One Sumerian form, me, is two different dictionary entries: a noun meaning '
     '"Being, divine properties", and the verb "to be".'),
    (8000, 12000,
     "Sources like these are reconciled by hand, because an AI answer hides where "
     "each claim came from, and can invent its evidence."),
    (20000, 10000,
     "So the model here is only allowed to propose."),
    (30000, 8000,
     "Muse Spark one point three read the entries and proposed twelve claims. Each "
     "carries its exact quote, and the model's interpretation, kept separate. That "
     "quote is highlighted in the source: located by code, not trusted from the model."),
    (44500, 7500,
     "Twelve proposals. Twelve quotes verified. And every item still reads: awaiting "
     "human decision. The model has approved nothing."),
    (52000, 13000,
     "Every proposal keeps its provenance: the document, the exact quote, the model "
     "and its prompt hash."),
    (65000, 13000,
     "Now a human decides. I accept this claim, as reviewer one."),
    (78000, 14000,
     "One reviewer is a decision. A second reviewer accepts the same claim, and only "
     "now does the system show community consensus: two of two reviewers."),
    (92000, 10000,
     "The decision lands in the registry, decided by two reviewers, with the full "
     "vote trail and an exportable record."),
    (102000, 7000,
     "AI proposes. Evidence challenges. Humans decide. FEN, human-governed AI synthesis."),
]


def load_env() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("ELEVENLABS_") and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit(
            "ELEVENLABS_API_KEY is not set. Add it to the repo-root .env "
            "(ELEVENLABS_API_KEY=sk_...) and re-run."
        )
    return key


def headers() -> dict:
    return {"xi-api-key": api_key(), "Content-Type": "application/json"}


def list_voices() -> list:
    resp = requests.get(f"{API}/voices", headers=headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("voices", [])


def pick_voice(voices: list) -> str:
    pinned = os.environ.get("ELEVENLABS_VOICE_ID")
    if pinned:
        return pinned
    cloned = [v for v in voices if v.get("category") == "cloned"]
    if len(cloned) == 1:
        print(f"Using cloned voice: {cloned[0]['name']} ({cloned[0]['voice_id']})")
        return cloned[0]["voice_id"]
    if len(cloned) > 1:
        print("Several cloned voices found — set ELEVENLABS_VOICE_ID to one of:")
        for v in cloned:
            print(f"  {v['voice_id']}  {v['name']}")
        sys.exit(2)
    print("No cloned voice found. Available voices:")
    for v in voices:
        print(f"  {v['voice_id']}  {v['name']}  [{v.get('category')}]")
    sys.exit(2)


def synthesize(voice_id: str, text: str, dest: Path) -> None:
    payload = {
        "text": text,
        "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }
    resp = requests.post(
        f"{API}/text-to-speech/{voice_id}",
        headers=headers(),
        json=payload,
        params={"output_format": "mp3_44100_128"},
        timeout=180,
    )
    if resp.status_code != 200:
        sys.exit(f"TTS failed ({resp.status_code}): {resp.text[:400]}")
    dest.write_bytes(resp.content)


def ffmpeg_exe() -> str:
    sys.path.insert(0, str(ROOT / ".vendor"))
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        found = subprocess.run(["where.exe", "ffmpeg"], capture_output=True, text=True)
        if found.returncode == 0 and found.stdout.strip():
            return found.stdout.strip().splitlines()[0]
        sys.exit("ffmpeg not found (expected .vendor/imageio_ffmpeg or PATH).")


def audio_duration_s(path: Path) -> float:
    out = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, errors="ignore",
    ).stderr
    for line in out.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = stamp.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def generate(voice_id: str) -> dict:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    for index, (start_ms, window_ms, text) in enumerate(SEGMENTS, start=1):
        dest = VOICE_DIR / f"{index:02d}.mp3"
        print(f"[{index}/10] {start_ms / 1000:6.1f}s  {text[:60]}…", flush=True)
        synthesize(voice_id, text, dest)
        duration = audio_duration_s(dest)
        overflow = duration * 1000 > window_ms
        report.append({
            "index": index, "start_ms": start_ms, "window_ms": window_ms,
            "duration_ms": int(duration * 1000), "overflow": overflow,
            "file": str(dest.relative_to(ROOT)),
        })
        if overflow:
            print(f"   ! longer than its window by "
                  f"{duration * 1000 - window_ms:.0f} ms — trim the text")
    (VOICE_DIR / "timings.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    total = sum(r["duration_ms"] for r in report)
    print(f"\nnarration total: {total / 1000:.1f}s of speech across 109s of video")
    return {"segments": report, "total_ms": total}


def assemble() -> None:
    if not VIDEO_IN.is_file():
        sys.exit(f"missing video: {VIDEO_IN}")
    parts, labels = [], []
    for index, (start_ms, _window, _text) in enumerate(SEGMENTS, start=1):
        src = VOICE_DIR / f"{index:02d}.mp3"
        if not src.is_file():
            sys.exit(f"missing segment: {src} (run --generate first)")
        parts.append(f"[{index}:a]adelay={start_ms}|{start_ms},volume=1.0[a{index}]")
        labels.append(f"[a{index}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:normalize=0,apad[aout]"
    cmd = [ffmpeg_exe(), "-y", "-i", str(VIDEO_IN)]
    for index in range(1, len(SEGMENTS) + 1):
        cmd += ["-i", str(VOICE_DIR / f"{index:02d}.mp3")]
    cmd += [
        "-filter_complex", graph,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest", str(VIDEO_OUT),
    ]
    print("assembling…", flush=True)
    done = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    if done.returncode != 0:
        print(done.stderr[-1500:])
        sys.exit("ffmpeg assembly failed")
    print(f"OK: {VIDEO_OUT}")
    print(f"duration: {audio_duration_s(VIDEO_OUT):.1f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="ElevenLabs voiceover for the demo")
    parser.add_argument("--list-voices", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--assemble", action="store_true")
    args = parser.parse_args()
    load_env()

    if args.list_voices:
        for v in list_voices():
            labels = v.get("labels") or {}
            print(f"{v['voice_id']}  {v['name']:<28} [{v.get('category')}] "
                  f"{labels.get('language', '')} {labels.get('accent', '')}")
        return 0

    if args.generate:
        generate(pick_voice(list_voices()))
    if args.assemble:
        assemble()
    if not (args.generate or args.assemble or args.list_voices):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
