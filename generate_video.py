"""
VideoAI.ng — generate_video.py

Topic -> narrated video with real stock footage.

Pipeline:
  1. LLM breaks the topic into timed narration segments.
     Provider waterfall: Groq -> OpenAI -> Gemini (thinking disabled,
     schema-constrained, tolerant JSON parsing) — matches your existing
     PROVIDER_ORDER and fixes the truncation issue at the Gemini leg.
  2. Each segment is voiced with gTTS; REAL duration is measured
     (never estimated) so visuals sync exactly to narration.
  3. Each segment's keywords fetch a real Pexels video clip. If none is
     found, Layer A deterministic fallback kicks in: a Ken Burns pan
     over a generated background with the segment text overlaid — so a
     bad search never breaks the render.
  4. FFmpeg trims/loops each clip to its segment's audio duration,
     concatenates them, and muxes in the full narration track.

Setup:
    pip install requests gtts pydub python-dotenv
    ffmpeg must be installed and on PATH.

    .env:
        GROQ_API_KEY=...
        OPENAI_API_KEY=...      # optional, used if Groq fails
        GEMINI_API_KEY=...      # optional, used if both above fail
        PEXELS_API_KEY=...      # free at pexels.com/api

Run:
    python generate_video.py --topic "The Rise of Netflix" --duration 60
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from gtts import gTTS
from pydub import AudioSegment

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")  # see Kokoro docs for full voice list

WIDTH, HEIGHT, FPS = 1920, 1080, 30
WORDS_PER_SECOND = 2.5  # ~150 wpm narration pace

WORKDIR = Path("workdir") / str(uuid.uuid4())[:8]

try:
    # Import PipelineConfig along with the pipeline
    from pykokoro import KokoroPipeline, PipelineConfig 
    import soundfile as sf
    import numpy as np

    # Configure pykokoro using PipelineConfig (specify an American English voice like 'am_michael')
    config = PipelineConfig(voice="am_michael") 
    _KOKORO_PIPELINE = KokoroPipeline(config)
    
    print("[ok] Kokoro TTS loaded")
except Exception as e:
    _KOKORO_PIPELINE = None
    print(f"[info] Kokoro not available ({e}); falling back to gTTS") 



# ---------------------------------------------------------------------------
# 1. Script generation — provider waterfall with the truncation fix
# ---------------------------------------------------------------------------

SEGMENT_SCHEMA_DESC = (
    'Respond with ONLY a JSON array, no prose, no markdown fences. '
    'Each element: {"text": "<narration sentence(s)>", '
    '"keywords": ["<visual search term>", "<alt term>"]}. '
    "keywords must be concrete, filmable nouns (e.g. 'stock market trading floor', "
    "'server room data center') — never abstract concepts."
)


def build_prompt(topic: str, target_words: int, num_segments: int) -> str:
    return (
        f"Write a documentary narration script about: {topic}\n"
        f"Total length: approximately {target_words} words, "
        f"split into exactly {num_segments} segments of roughly equal length.\n"
        f"The first segment must be a strong hook. The last must land the point, "
        f"not trail off.\n"
        f"{SEGMENT_SCHEMA_DESC}"
    )


def _parse_json_tolerant(text: str) -> Optional[list]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    repaired = text
    if repaired.count('"') % 2 == 1:
        repaired += '"'
    depth = repaired.count("[") - repaired.count("]")
    if depth > 0:
        repaired += "]" * depth
    depth = repaired.count("{") - repaired.count("}")
    if depth > 0:
        repaired += "}" * depth
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def try_groq(prompt: str) -> Optional[list]:
    if not GROQ_API_KEY:
        return None
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _parse_json_tolerant(text)
    except Exception as e:
        print(f"[warn] Groq failed: {e}")
        return None


def try_openai(prompt: str) -> Optional[list]:
    if not OPENAI_API_KEY:
        return None
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _parse_json_tolerant(text)
    except Exception as e:
        print(f"[warn] OpenAI failed: {e}")
        return None


def try_gemini(prompt: str) -> Optional[list]:
    if not GEMINI_API_KEY:
        return None
    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingBudget": 0},  # the fix: no hidden
                    "maxOutputTokens": 2048,                   # reasoning tokens
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_json_tolerant(text)
    except Exception as e:
        print(f"[warn] Gemini failed: {e}")
        return None


def generate_script(topic: str, duration: int) -> list[dict]:
    target_words = int(duration * WORDS_PER_SECOND)
    num_segments = max(3, round(duration / 10))  # ~1 segment per 10s
    prompt = build_prompt(topic, target_words, num_segments)

    for provider_fn, name in [
        (try_groq, "Groq"),
        (try_openai, "OpenAI"),
        (try_gemini, "Gemini"),
    ]:
        segments = provider_fn(prompt)
        if segments and isinstance(segments, list) and len(segments) > 0:
            print(f"[ok] script generated via {name} ({len(segments)} segments)")
            return segments

    raise RuntimeError(
        "All providers failed to produce a usable script. "
        "Check API keys and quota."
    )


# ---------------------------------------------------------------------------
# 2. Voice synthesis — real measured duration, not estimated
# ---------------------------------------------------------------------------

def _synthesize_kokoro(text: str, path: Path) -> None:
    """Synthesizes text using pykokoro and saves the full audio 
    directly without requiring manual chunk concatenation."""
    # pykokoro automatically parses text, handles chunks, and applies voice properties
    result = _KOKORO_PIPELINE.run(text)
    
    # Save the output directly using the pipeline's native sample rate
    sf.write(str(path), result.audio, result.sample_rate)



def synthesize_audio(segments: list[dict]) -> None:
    audio_dir = WORKDIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, seg in enumerate(segments):
        if _KOKORO_PIPELINE is not None:
            path = audio_dir / f"seg_{i:02d}.wav"
            _synthesize_kokoro(seg["text"], path)
        else:
            path = audio_dir / f"seg_{i:02d}.mp3"
            gTTS(text=seg["text"], lang="en").save(str(path))

        duration = len(AudioSegment.from_file(path)) / 1000.0
        seg["audio_path"] = str(path)
        seg["duration"] = round(duration, 2)
        print(f"[ok] segment {i}: {duration:.1f}s narration")


# ---------------------------------------------------------------------------
# 3. Visual acquisition — real footage first, deterministic fallback second
# ---------------------------------------------------------------------------

def fetch_pexels_clip(query: str, dest: Path) -> bool:
    if not PEXELS_API_KEY:
        return False
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 5, "orientation": "landscape"},
            timeout=20,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            return False
        # Prefer an HD file close to our target resolution.
        files = sorted(
            videos[0]["video_files"],
            key=lambda f: abs((f.get("width") or 0) - WIDTH),
        )
        video_url = files[0]["link"]
        with requests.get(video_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                shutil.copyfileobj(r.raw, f)
        return True
    except Exception as e:
        print(f"[warn] Pexels fetch failed for '{query}': {e}")
        return False


def make_fallback_clip(text: str, duration: float, dest: Path) -> None:
    """Layer A deterministic fallback: Ken Burns pan over a solid background
    with the segment text overlaid. Guarantees a segment always renders."""
    safe_text = text.replace("'", "").replace(":", "-")[:90]
    filter_chain = (
        f"color=c=0x1a1a2e:s={WIDTH}x{HEIGHT}:d={duration}:r={FPS},"
        f"zoompan=z='min(zoom+0.0008,1.15)':d={int(duration*FPS)}:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"drawtext=text='{safe_text}':fontcolor=white:fontsize=48:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.4:boxborderw=20"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", filter_chain,
            "-t", str(duration), "-pix_fmt", "yuv420p", str(dest),
        ],
        check=True, capture_output=True,
    )


def acquire_visuals(segments: list[dict]) -> None:
    clips_dir = WORKDIR / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    for i, seg in enumerate(segments):
        raw_path = clips_dir / f"raw_{i:02d}.mp4"
        query = seg["keywords"][0] if seg.get("keywords") else seg["text"][:40]
        found = fetch_pexels_clip(query, raw_path)
        if not found:
            print(f"[fallback] segment {i}: using Ken Burns fallback for '{query}'")
            make_fallback_clip(seg["text"], seg["duration"], raw_path)
            seg["is_fallback"] = True
        seg["raw_clip"] = str(raw_path)


# ---------------------------------------------------------------------------
# 4. Render — trim/loop each clip to its segment's exact audio duration
# ---------------------------------------------------------------------------

def normalize_segment_clip(seg: dict, index: int) -> Path:
    clips_dir = WORKDIR / "clips"
    out_path = clips_dir / f"norm_{index:02d}.mp4"
    duration = seg["duration"]

    if seg.get("is_fallback"):
        # Already exactly the right duration and resolution.
        shutil.copy(seg["raw_clip"], out_path)
        return out_path

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", seg["raw_clip"],
            "-t", str(duration),
            "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                   f"crop={WIDTH}:{HEIGHT},fps={FPS}",
            "-an", "-pix_fmt", "yuv420p", str(out_path),
        ],
        check=True, capture_output=True,
    )
    return out_path


def render_final_video(segments: list[dict], output_path: Path) -> None:
    normalized = [normalize_segment_clip(s, i) for i, s in enumerate(segments)]

    concat_list = WORKDIR / "concat_list.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in normalized)
    )
    silent_video = WORKDIR / "video_silent.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c", "copy", str(silent_video),
        ],
        check=True, capture_output=True,
    )

    full_narration = sum(
        (AudioSegment.from_file(s["audio_path"]) for s in segments),
        AudioSegment.empty(),
    )
    narration_path = WORKDIR / "narration.mp3"
    full_narration.export(narration_path, format="mp3")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(silent_video), "-i", str(narration_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            str(output_path),
        ],
        check=True, capture_output=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--out", default="output.mp4")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH — install it before running this.")

    WORKDIR.mkdir(parents=True, exist_ok=True)
    print(f"[1/4] Generating script for: {args.topic}")
    segments = generate_script(args.topic, args.duration)

    print("[2/4] Synthesizing narration")
    synthesize_audio(segments)

    print("[3/4] Acquiring visuals")
    acquire_visuals(segments)

    print("[4/4] Rendering final video")
    output_path = Path(args.out)
    render_final_video(segments, output_path)

    print(f"\nDone: {output_path.resolve()}")
    print(f"Working files kept in: {WORKDIR.resolve()} (delete when done inspecting)")


if __name__ == "__main__":
    main()