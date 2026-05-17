import json
import subprocess
from pathlib import Path
from config import ELEVENLABS_API_KEY, OUTPUT_DIR

# ── ELEVENLABS (uncomment when you have a paid plan) ─────────────────────────
# from elevenlabs.client import ElevenLabs
# eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY) if ELEVENLABS_API_KEY else None
# ─────────────────────────────────────────────────────────────────────────────


async def generate_audio(narration: str, job_id: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM") -> Path:
    audio_path = OUTPUT_DIR / f"{job_id}_audio.mp3"

    # ── Option A: ElevenLabs (best quality — needs paid plan) ────────────────
    # if ELEVENLABS_API_KEY and eleven_client:
    #     try:
    #         audio_generator = eleven_client.text_to_speech.convert(
    #             voice_id=voice_id,
    #             text=narration,
    #             model_id="eleven_multilingual_v2",
    #             voice_settings={"stability": 0.5, "similarity_boost": 0.8},
    #         )
    #         with open(audio_path, "wb") as f:
    #             for chunk in audio_generator:
    #                 if chunk:
    #                     f.write(chunk)
    #         return audio_path
    #     except Exception as e:
    #         raise ValueError(f"ElevenLabs failed: {e}")

    # ── Option B: gTTS — free, no key needed ─────────────────────────────────
    # tld options:
    #   "co.uk"  = British English (crisp, professional) ← current
    #   "com"    = American English (slower)
    #   "co.in"  = Indian English
    #   "com.au" = Australian English
    try:
        from gtts import gTTS
        tts = gTTS(text=narration, lang="en", tld="co.uk", slow=False)
        tts.save(str(audio_path))
        return audio_path
    except Exception as e:
        raise ValueError(f"gTTS failed: {e}")


def get_audio_duration(audio_path: Path) -> float:
    """Use ffprobe to get exact audio duration in seconds."""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(audio_path)
    ], capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    for stream in info.get("streams", []):
        if "duration" in stream:
            return float(stream["duration"])
    raise ValueError("Could not determine audio duration from ffprobe")