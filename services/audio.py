import json
import subprocess
import logging
from pathlib import Path
from typing import Optional
from config import ELEVENLABS_API_KEY, OUTPUT_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── VOICE OPTIONS ───────────────────────────────────────────────────────────
VOICE_OPTIONS = {
    "female_warm": "af_sarah",
    "female_professional": "af_nicole",
    "male_deep": "am_adam",
    "female_energetic": "af_bella",
}

# ── KOKORO PIPELINE INITIALIZATION (ONCE AT MODULE LEVEL) ──────────────────
try:
    from pykokoro import KokoroPipeline, PipelineConfig
    kokoro_pipeline = KokoroPipeline(PipelineConfig(voice="bf_emma"))
    logger.info("Kokoro TTS pipeline initialized successfully")
except Exception as e:
    kokoro_pipeline = None
    logger.warning(f"Kokoro TTS failed to initialize: {e} — will fall back to gTTS")


async def generate_audio(narration: str, job_id: str, voice_id: Optional[str] = None) -> Path:
    global kokoro_pipeline
    audio_path = OUTPUT_DIR / f"{job_id}_audio.wav"
    
    # ── Option A: Kokoro TTS (high quality) ───────────────────────────────
    if kokoro_pipeline:
        try:
            import numpy as np
            import soundfile as sf
            
            # Map voice_id to Kokoro voice or use default
            kokoro_voice = VOICE_OPTIONS.get(voice_id, "bf_emma") if voice_id else "bf_emma"
            
            # Update pipeline voice if needed
            if kokoro_pipeline.config.voice != kokoro_voice:
                from pykokoro import PipelineConfig
                kokoro_pipeline = KokoroPipeline(PipelineConfig(voice=kokoro_voice))
            
            # Generate audio
            res = kokoro_pipeline.run(narration)
            
            # Save as WAV
            sf.write(str(audio_path), res.audio, samplerate=res.sample_rate)
            
            logger.info(f"Generated audio with Kokoro TTS: {audio_path}")
            return audio_path
        except Exception as e:
            logger.error(f"Kokoro TTS failed: {e} — falling back to gTTS")
    
    # ── Option B: gTTS (fallback) ──────────────────────────────────────────
    try:
        from gtts import gTTS
        # gTTS saves as mp3, change path extension
        mp3_path = OUTPUT_DIR / f"{job_id}_audio.mp3"
        tts = gTTS(text=narration, lang="en", tld="co.uk", slow=False)
        tts.save(str(mp3_path))
        logger.info(f"Generated audio with gTTS fallback: {mp3_path}")
        return mp3_path
    except Exception as e:
        raise ValueError(f"All TTS options failed: {e}")


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
