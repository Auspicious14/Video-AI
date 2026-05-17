"""
VideoAI — FastAPI Application Entry Point
Version: 3.0.0

Architecture: Hybrid Video System
  Layer A: Deterministic FFmpeg composition (always works)
  Layer B: AI asset generation — Gemini script, gTTS audio, FLUX.1-schnell images
  Layer C: AI motion enhancement — HuggingFace Wan2.1 / CogVideoX (optional)

Endpoints:
  POST /generate/hybrid        — Primary: full hybrid pipeline
  POST /generate/tiktok        — Legacy: backward-compatible TikTok pipeline
  POST /generate/still-to-motion — Upload image → animated Ken Burns
  POST /generate/ai-video      — Layer C primary with Ken Burns fallback
  POST /generate/motion-design — Remotion (coming soon)
  GET  /generate/jobs/{job_id} — Poll status + progress (0-100)
  GET  /outputs/{filename}     — Serve generated videos
  POST /payments/*             — Paystack payment integration
  GET  /credits/{email}        — Credit balance
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import FRONTEND_URL, OUTPUT_DIR
from routers import videos, payments, credits
from services.avatar import is_wav2lip_ready

app = FastAPI(
    title="VideoAI API",
    version="3.0.0",
    description=(
        "Hybrid AI video generation: deterministic FFmpeg composition + "
        "HuggingFace AI assets. No paid APIs required."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated videos
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# Register routers
app.include_router(videos.router)
app.include_router(payments.router)
app.include_router(credits.router)


@app.get("/health", tags=["system"])
def health():
    """System health check — returns version and infrastructure status."""
    from config import DEV_MODE, GEMINI_API_KEY, HF_API_KEY
    return {
        "status":      "ok",
        "version":     "3.0.0",
        "dev_mode":    DEV_MODE,
        "gemini":      bool(GEMINI_API_KEY),
        "huggingface": bool(HF_API_KEY),
        "architecture": {
            "layer_a": "FFmpeg deterministic composition — always available",
            "layer_b": "FLUX.1-schnell + gTTS — requires HF_API_KEY",
            "layer_c": "Wan2.1 / CogVideoX-5B — optional, HF free tier",
        },
        "wav2lip": is_wav2lip_ready(),
    }