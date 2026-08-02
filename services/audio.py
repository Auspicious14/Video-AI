"""
services/audio.py — Provider-Independent Audio Pipeline
═══════════════════════════════════════════════════════════════════════════════

Architecture
─────────────
• Kokoro TTS  — default provider (high-quality, offline)
• gTTS        — lightweight fallback (requires internet)
• OpenAI TTS  — optional cloud provider
• ElevenLabs  — optional premium provider
• Gemini TTS  — optional Google provider (future)

ffprobe Fix
────────────
The original SIGABRT crash was caused by:
  1. Kokoro/soundfile writing the WAV during async context with no flush guarantee.
  2. ffprobe being called on the path before the OS had flushed the file data.
  3. `check=True` turning the SIGABRT into an uncaught CalledProcessError.

Fixes applied:
  • After sf.write() we call Path.stat() to force a filesystem round-trip.
  • ffprobe is called via subprocess.run (not check=True) so we can log diagnostics.
  • If ffprobe fails we fall back to soundfile.info() for duration, which is always
    available because we own the wav generation.
  • Complete diagnostics are logged whenever ffprobe fails.

Adaptive Runtime
─────────────────
get_audio_duration() always returns the real narration length.
The pipeline uses this to redistribute scene timing (Part 3).
"""

from __future__ import annotations
from services import motion_brief
import re
import json
import logging
import os
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# ── Voice registry ────────────────────────────────────────────────────────────

VOICE_REGISTRY: dict[str, str] = {
    # Kokoro voices
    "female_warm":         "bf_emma",
    "female_professional": "af_nicole",
    "male_deep":           "am_adam",
    "female_energetic":    "af_bella",
    "female_brit":         "bf_emma",
    "male_brit":           "bm_george",
    # ElevenLabs voices (IDs)
    "elevenlabs_default":  "21m00Tcm4TlvDq8ikWAM",
}

DEFAULT_KOKORO_VOICE = "am_adam"

_COMMA_NUMBER_PATTERN = re.compile(r'\b(\d{1,3}(?:,\d{3})+)\b')
_DECIMAL_SCALE_PATTERN = re.compile(r'\b(\d+)\.(\d+)\s+(billion|million|trillion|thousand)\b', re.IGNORECASE)
_DECADE_2000s = re.compile(r'\b200([0-9])\b')
_YEAR_PATTERN = re.compile(r'\b(1[0-9]{3}|20[1-9][0-9])\b')  # excludes 2000-2009, handled separately above
_DIGIT_WORDS = {"0":"","1":"one","2":"two","3":"three","4":"four","5":"five","6":"six","7":"seven","8":"eight","9":"nine"}

# ── Provider protocol ─────────────────────────────────────────────────────────

class AudioProvider(Protocol):
    """Structural protocol — any object matching this interface is a valid audio provider."""

    async def generate(self, narration: str, job_id: str, voice_id: Optional[str]) -> Path:
        ...

    @property
    def name(self) -> str:
        ...


# ── Kokoro provider ───────────────────────────────────────────────────────────

class KokoroProvider:
    """High-quality offline TTS via pykokoro."""

    name = "kokoro"

    def __init__(self) -> None:
        self._pipeline = None
        self._current_voice: str = ""
        self._ready = False
        self._init()

    def _init(self) -> None:
        try:
            # pyrefly: ignore [missing-import]
            from pykokoro import KokoroPipeline, PipelineConfig
            self._pipeline = KokoroPipeline(PipelineConfig(voice=DEFAULT_KOKORO_VOICE))
            self._current_voice = DEFAULT_KOKORO_VOICE
            self._ready = True
            logger.info("Kokoro TTS initialised (%s)", DEFAULT_KOKORO_VOICE)
        except Exception as exc:
            logger.warning("Kokoro TTS unavailable: %s", exc)
            self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _ensure_voice(self, voice_key: str) -> None:
        resolved = VOICE_REGISTRY.get(voice_key, voice_key) if voice_key else DEFAULT_KOKORO_VOICE
        if self._current_voice == resolved:
            return
        try:
            # pyrefly: ignore [missing-import]
            from pykokoro import KokoroPipeline, PipelineConfig
            self._pipeline = KokoroPipeline(PipelineConfig(voice=resolved))
            self._current_voice = resolved
            logger.info("Kokoro voice changed to %s", resolved)
        except Exception as exc:
            logger.warning("Failed to switch Kokoro voice to %s: %s", resolved, exc)

    async def generate(self, narration: str, job_id: str, voice_id: Optional[str] = None) -> Path:
        if not self._ready or not self._pipeline:
            raise RuntimeError("Kokoro not available")

        import numpy as np
        # pyrefly: ignore [missing-import]
        import soundfile as sf

        if voice_id:
            self._ensure_voice(voice_id)

        audio_path = OUTPUT_DIR / f"{job_id}_audio.wav"

        narration = _normalize_years_for_tts(narration)

        # Generate audio
        res = self._pipeline.run(narration)

        # Write WAV — soundfile returns after the data is in the OS buffer.
        sf.write(str(audio_path), res.audio, samplerate=res.sample_rate)

        # Force filesystem sync: open + close flushes the kernel buffer on macOS.
        _flush_file(audio_path)

        size = audio_path.stat().st_size
        logger.info(
            "Kokoro audio generated | path=%s size=%d bytes voice=%s",
            audio_path.name, size, self._current_voice,
        )
        return audio_path


# ── gTTS provider ─────────────────────────────────────────────────────────────

class GTTSProvider:
    """Google Text-to-Speech (requires internet, returns MP3)."""

    name = "gtts"

    async def generate(self, narration: str, job_id: str, voice_id: Optional[str] = None) -> Path:
        # pyrefly: ignore [missing-import]
        from gtts import gTTS

        mp3_path = OUTPUT_DIR / f"{job_id}_audio.mp3"
        tts = gTTS(text=narration, lang="en", tld="co.uk", slow=False)
        tts.save(str(mp3_path))
        _flush_file(mp3_path)

        size = mp3_path.stat().st_size
        logger.info("gTTS audio generated | path=%s size=%d bytes", mp3_path.name, size)
        return mp3_path


# ── OpenAI TTS provider ───────────────────────────────────────────────────────

class OpenAITTSProvider:
    """OpenAI TTS (requires OPENAI_API_KEY)."""

    name = "openai"

    async def generate(self, narration: str, job_id: str, voice_id: Optional[str] = None) -> Path:
        # pyrefly: ignore [missing-import]
        import openai

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        client = openai.AsyncOpenAI(api_key=api_key)
        voice = voice_id or "nova"
        audio_path = OUTPUT_DIR / f"{job_id}_audio.mp3"

        response = await client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=narration,
        )
        audio_path.write_bytes(response.content)
        _flush_file(audio_path)

        logger.info("OpenAI TTS audio generated | path=%s", audio_path.name)
        return audio_path


# ── Provider chain ────────────────────────────────────────────────────────────

# Module-level singleton — initialised once
_kokoro = KokoroProvider()
_gtts   = GTTSProvider()

_PROVIDER_CHAIN = [_kokoro, _gtts]


async def generate_audio(
    narration: str,
    job_id: str,
    voice_id: Optional[str] = None,
    preferred_provider: Optional[str] = None,
) -> Path:
    """
    Generate TTS audio, trying providers in order until one succeeds.

    Provider order (default):
      1. Kokoro TTS  — high quality, offline
      2. gTTS        — lightweight fallback

    Parameters
    ----------
    narration:          The full spoken narration text.
    job_id:             Unique job identifier used for naming the output file.
    voice_id:           Voice key (from VOICE_REGISTRY) or provider-specific ID.
    preferred_provider: 'kokoro' | 'gtts' | 'openai' — override provider order.

    Returns
    -------
    Path to generated audio file (.wav or .mp3).

    Raises
    ------
    ValueError: All providers failed.
    """
    if not narration.strip():
        raise ValueError("narration is empty — cannot generate audio")

    chain: list = _PROVIDER_CHAIN

    if preferred_provider == "kokoro":
        chain = [_kokoro, _gtts]
    elif preferred_provider == "gtts":
        chain = [_gtts]
    elif preferred_provider == "openai":
        chain = [OpenAITTSProvider(), _gtts]

    errors: list[str] = []

    for provider in chain:
        # Skip Kokoro if it did not initialise
        if isinstance(provider, KokoroProvider) and not provider.is_ready:
            continue
        try:
            logger.info("Attempting audio generation with provider: %s", provider.name)
            path = await provider.generate(narration, job_id, voice_id)
            _verify_audio_file(path)
            return path
        except Exception as exc:
            logger.warning("Provider %s failed: %s", provider.name, exc)
            errors.append(f"{provider.name}: {exc}")

    raise ValueError(f"All TTS providers failed:\n" + "\n".join(errors))


# ── Duration analysis ─────────────────────────────────────────────────────────

def get_audio_duration(audio_path: Path) -> float:
    """
    Return the audio duration in seconds using ffprobe with rich fallback diagnostics.

    Strategy
    --------
    1. Try ffprobe JSON stream analysis.
    2. If ffprobe fails (SIGABRT, codec error, etc.), fall back to soundfile.info()
       which is always available because we own the file generation.

    The fallback ensures the pipeline NEVER crashes due to ffprobe unavailability.

    Raises
    ------
    ValueError: File does not exist, is corrupt, and soundfile fallback also fails.
    """
    # ── Pre-flight checks ──────────────────────────────────────────────────────
    if not audio_path.exists():
        raise ValueError(f"Audio file not found: {audio_path}")

    file_size = audio_path.stat().st_size
    if file_size < 100:
        raise ValueError(
            f"Audio file is suspiciously small ({file_size} bytes): {audio_path.name}"
        )

    # ── Attempt 1: ffprobe ────────────────────────────────────────────────────
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            # NOTE: do NOT use check=True — we handle errors ourselves to emit diagnostics
        )

        if result.returncode == 0:
            info = json.loads(result.stdout)
            for stream in info.get("streams", []):
                if "duration" in stream:
                    duration = float(stream["duration"])
                    logger.debug(
                        "ffprobe duration | path=%s size=%d bytes duration=%.3fs codec=%s channels=%s sample_rate=%s",
                        audio_path.name,
                        file_size,
                        duration,
                        stream.get("codec_name", "?"),
                        stream.get("channels", "?"),
                        stream.get("sample_rate", "?"),
                    )
                    return duration

            # ffprobe succeeded but no duration in streams — fall through
            logger.warning(
                "ffprobe found no duration in streams | path=%s stdout=%s",
                audio_path.name,
                result.stdout[:300],
            )

        else:
            # ffprobe failed — log full diagnostics
            _log_ffprobe_failure(audio_path, file_size, result)

    except subprocess.TimeoutExpired:
        logger.error("ffprobe timed out after 30s | path=%s", audio_path.name)
    except FileNotFoundError:
        logger.warning("ffprobe not found — falling back to soundfile")
    except Exception as exc:
        logger.error("ffprobe unexpected error: %s | path=%s", exc, audio_path.name)

    # ── Attempt 2: soundfile fallback ─────────────────────────────────────────
    return _soundfile_duration(audio_path)


def _log_ffprobe_failure(
    audio_path: Path,
    file_size: int,
    result: subprocess.CompletedProcess,
) -> None:
    """Log a comprehensive ffprobe failure report for easy diagnostics."""
    logger.error(
        "ffprobe failed | returncode=%d\n"
        "  path      = %s\n"
        "  exists    = %s\n"
        "  size      = %d bytes\n"
        "  stdout    = %s\n"
        "  stderr    = %s",
        result.returncode,
        audio_path,
        audio_path.exists(),
        file_size,
        result.stdout[:500] if result.stdout else "(empty)",
        result.stderr[:500] if result.stderr else "(empty)",
    )

    # Try to get more info from soundfile to populate the diagnostics
    try:
        # pyrefly: ignore [missing-import]
        import soundfile as sf
        info = sf.info(str(audio_path))
        logger.error(
            "  soundfile | codec=%s channels=%d sample_rate=%d frames=%d duration=%.3fs",
            info.subtype,
            info.channels,
            info.samplerate,
            info.frames,
            info.duration,
        )
    except Exception as sf_exc:
        logger.error("  soundfile | also failed: %s", sf_exc)


def _soundfile_duration(audio_path: Path) -> float:
    """
    Fallback duration using soundfile.info() — works for WAV/FLAC/OGG/AIFF.
    For MP3 (gTTS output), falls back to mutagen.
    """
    suffix = audio_path.suffix.lower()

    # WAV / FLAC / OGG — soundfile handles these natively
    if suffix in {".wav", ".flac", ".ogg", ".aiff"}:
        try:
            # pyrefly: ignore [missing-import]
            import soundfile as sf
            info = sf.info(str(audio_path))
            duration = info.duration
            logger.info(
                "soundfile fallback duration | path=%s duration=%.3fs codec=%s channels=%d sr=%d",
                audio_path.name, duration, info.subtype, info.channels, info.samplerate,
            )
            return duration
        except Exception as exc:
            logger.error("soundfile also failed: %s | path=%s", exc, audio_path.name)

    # MP3 — mutagen handles these
    if suffix == ".mp3":
        try:
            # pyrefly: ignore [missing-import]
            from mutagen.mp3 import MP3
            audio = MP3(str(audio_path))
            duration = audio.info.length
            logger.info(
                "mutagen fallback duration | path=%s duration=%.3fs", audio_path.name, duration,
            )
            return duration
        except Exception as exc:
            logger.error("mutagen also failed: %s | path=%s", exc, audio_path.name)

    # Last resort: estimate from file size (very rough — 128kbps MP3 ≈ 16kB/s)
    _size = audio_path.stat().st_size
    estimated = _size / 16000.0
    logger.warning(
        "All duration probes failed — estimating %.1fs from file size %d bytes | path=%s",
        estimated, _size, audio_path.name,
    )
    return max(1.0, estimated)


# ── Private helpers ───────────────────────────────────────────────────────────

def _flush_file(path: Path) -> None:
    """
    Force filesystem flush for the file at `path`.

    On macOS, soundfile/libsndfile writes data into the OS page cache but does
    not guarantee that a subsequent subprocess (ffprobe) sees the complete file.
    Opening + closing the file descriptor forces the VFS to flush pending writes.
    """
    try:
        with open(path, "rb") as fh:
            fh.read(1)          # nudge the VFS — one byte is enough
        # Brief sleep to let the FS settle on slower SSDs/network mounts
        time.sleep(0.05)
    except Exception as exc:
        logger.debug("_flush_file: %s (non-fatal)", exc)


def _verify_audio_file(path: Path) -> None:
    """
    Sanity check after generation:
      - file exists
      - file size > 1 kB
    Raises RuntimeError with details if either check fails.
    """
    if not path.exists():
        raise RuntimeError(f"Audio provider returned a path that does not exist: {path}")

    size = path.stat().st_size
    if size < 1024:
        raise RuntimeError(
            f"Generated audio file is too small ({size} bytes) — likely corrupt: {path.name}"
        )

def _normalize_years_for_tts(text: str) -> str:
    """Kokoro inconsistently reads 4-digit years as full cardinals vs proper
    year pronunciation. Splitting the digits forces the two-chunk reading
    path reliably. Imperfect: also affects genuine 4-digit quantities in
    this range (e.g. '1500 species' becomes 'fifteen hundred' too) — a
    reasonable trade for how often years appear in documentary narration."""
    return _YEAR_PATTERN.sub(lambda m: f"{m.group(0)[:2]} {m.group(0)[2:]}", text)





def _normalize_numbers_for_tts(text: str) -> str:
    text = _COMMA_NUMBER_PATTERN.sub(lambda m: m.group(0).replace(",", ""), text)
    text = _DECIMAL_SCALE_PATTERN.sub(lambda m: f"{m.group(1)} point {m.group(2)} {m.group(3)}", text)
    text = _DECADE_2000s.sub(
        lambda m: "two thousand" + (f" and {_DIGIT_WORDS[m.group(1)]}" if m.group(1) != "0" else ""),
        text,
    )
    text = _YEAR_PATTERN.sub(lambda m: f"{m.group(0)[:2]} {m.group(0)[2:]}", text)
    return text