import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── AI ────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
CEREBRAS_API_KEY   = os.getenv("CEREBRAS_API_KEY", "")
MISTRAL_API_KEY    = os.getenv("MISTRAL_API_KEY", "")
AGENTROUTER_API_KEY = os.getenv("AGENTROUTER_API_KEY", "")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")   # optional — leave blank for gTTS
HF_API_KEY         = os.getenv("HF_API_KEY", "")            # free token: huggingface.co/settings/tokens
FAL_KEY            = os.getenv("FAL_KEY", "")               # fal.ai API key for FLUX.1-dev
PIXAZO_API_KEY     = os.getenv("PIXAZO_API_KEY", "")       # pixazo API key for FLUX.1-schnell

# ── Payments ──────────────────────────────────────────────────────────────────
PAYSTACK_SECRET_KEY   = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_CALLBACK_URL = os.getenv("PAYSTACK_CALLBACK_URL", "http://localhost:3000/payment/verify")

# ── App ───────────────────────────────────────────────────────────────────────
FRONTEND_URL  = os.getenv("FRONTEND_URL", "*")
OUTPUT_DIR    = Path(os.getenv("OUTPUT_DIR", "outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Clip cache — stores AI-generated clips to avoid re-generation
CLIP_CACHE_DIR = OUTPUT_DIR / "clip_cache"
CLIP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Dev mode ──────────────────────────────────────────────────────────────────
# Set DEV_MODE = False and remove free credits before going live
DEV_MODE         = os.getenv("DEV_MODE", "true").lower() == "true"
DEV_FREE_CREDITS = int(os.getenv("DEV_FREE_CREDITS", "10"))

# ── Video rendering constants ─────────────────────────────────────────────────
# These match renderer.py — do not change without updating renderer.py too
VIDEO_FPS    = 30
VIDEO_WIDTH  = 576    # 9:16 portrait
VIDEO_HEIGHT = 1024

# ── Credit plans ──────────────────────────────────────────────────────────────
PLANS = {
    "starter":  {"amount": 250000,  "credits": 5,  "label": "Starter ₦2,500"},
    "pro":      {"amount": 500000,  "credits": 15, "label": "Pro ₦5,000"},
    "business": {"amount": 1200000, "credits": 50, "label": "Business ₦12,000"},
}


PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

UNSPLASH_ACCESS_KEY= os.getenv("UNSPLASH_ACCESS_KEY", "")
UNSPLASH_SECRET_KEY= os.getenv("UNSPLASH_SECRET_KEY", "")
UNSPLASH_APP_ID= os.getenv("UNSPLASH_APP_ID", "")
POLLINATIONS_API_KEY= os.getenv("POLLINATIONS_API_KEY", "")