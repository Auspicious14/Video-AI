# VideoAI.ng

AI video generator for TikTok clips, awareness videos, and motion graphics.
Pay in Naira via Paystack.

---

## Quick Start

### 1. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install FFmpeg (required)
# Ubuntu/Debian:
sudo apt install ffmpeg espeak

# macOS:
brew install ffmpeg espeak

# Copy and fill in your keys
cp .env.example .env
```

Edit `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...         # from console.anthropic.com
ELEVENLABS_API_KEY=...               # from elevenlabs.io (optional, has free tier)
PAYSTACK_SECRET_KEY=sk_test_...      # from dashboard.paystack.com
PAYSTACK_CALLBACK_URL=http://localhost:3000/payment/verify
FRONTEND_URL=http://localhost:3000
```

Start the backend:
```bash
uvicorn main:app --reload --port 8000
```

### 2. Frontend setup

Open `frontend/index.html` directly in your browser, OR serve it:

```bash
cd frontend
npx serve .     # serves on http://localhost:3000
```

---

## How it works

1. User enters topic, tone, duration → clicks Generate
2. Backend calls Claude API to write script (scenes + narration)
3. Backend calls ElevenLabs (or espeak) to generate voiceover MP3
4. Backend calls Pollinations.ai (free) to generate scene images
5. FFmpeg zoompan (Ken Burns effect) + merge audio + text overlay → MP4
6. Frontend polls job status and shows video when ready

---

## LLM providers (script writing + everything else)

The engine tries providers in order and falls through to the next one on rate
limits, timeouts or an empty balance.

| Job | Default order | Env var |
|-----|---------------|---------|
| Narration / script | `claude_cli` → `deepseek` → normal chain | `SCRIPT_PROVIDER_ORDER` |
| Everything else (research, visual plan, titles, SEO, JSON) | `deepseek` → `groq` → `mistral` → `gemini` → `agentrouter` | `PROVIDER_ORDER` |

Providers without a key are skipped automatically.

```
# DeepSeek — prepaid, pay-as-you-go (platform.deepseek.com)
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-flash        # or deepseek-v4-pro (stronger, pricier)
DEEPSEEK_THINKING=disabled           # "enabled" = slower, more tokens

# Claude via your Claude plan (Pro/Max) using the Claude Code CLI — local only
CLAUDE_CLI_ENABLED=true
CLAUDE_CLI_MODEL=sonnet              # or opus
# CLAUDE_CLI_PATH=claude             # if the binary is not on PATH
# CLAUDE_CLI_TIMEOUT=300
# CLAUDE_CLI_COOLDOWN_SECONDS=1800   # skip the CLI this long after a usage-limit error
```

### Using `claude -p` with your Claude plan

1. Install Claude Code: `npm install -g @anthropic-ai/claude-code`
2. Run `claude` once and log in with your Claude account (choose your
   subscription, not an API key).
3. Set `CLAUDE_CLI_ENABLED=true` in `.env`.

Notes:
- Make sure `ANTHROPIC_API_KEY` is **not** what you want to bill — the engine
  removes it from the CLI's environment so the CLI uses your plan.
- This draws on your plan's usage limits. When you hit the limit, narration
  falls back to DeepSeek automatically and the CLI is rested for 30 minutes.
- It runs on **your machine only**. It is for your own channel, not for
  serving other users of VideoAI.ng — use the Claude API for that.

---

## Deployment

### Backend (Render.com free tier)
1. Push backend/ to a GitHub repo
2. Create a new Web Service on render.com
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables in Render dashboard

### Frontend
- Deploy `frontend/` to Vercel, Netlify, or GitHub Pages (free)
- Update `const API = '...'` in index.html to your Render backend URL

---

## Paystack Setup

1. Sign up at dashboard.paystack.com
2. Get your test keys first (sk_test_...)
3. Set webhook URL in Paystack dashboard → Settings → Webhooks:
   `https://your-backend.onrender.com/payments/webhook`
4. Switch to live keys (sk_live_...) when ready

---

## Video types roadmap

- [x] TikTok awareness clips (script + voiceover + images + FFmpeg)
- [ ] Still image → motion (Ken Burns FFmpeg — easy to add)
- [ ] Prompt-to-video (same pipeline, more scenes)
- [ ] Motion design (Remotion — Phase 3)

---

## Adding more credits (in-memory vs database)

The current code uses a Python dict for credits — fine for testing.
For production, replace with SQLite or Postgres:

```python
# Replace user_credits dict with DB calls
import sqlite3
# or use SQLAlchemy + async
```

---

## Tech stack

| Layer     | Tool                         |
|-----------|------------------------------|
| Backend   | Python FastAPI               |
| Video     | FFmpeg (native)              |
| Script AI | Claude (Anthropic API)       |
| Voice     | ElevenLabs / espeak fallback |
| Images    | Pollinations.ai (free)       |
| Payments  | Paystack (Naira)             |
| Frontend  | Vanilla HTML/CSS/JS          |
| Hosting   | Render.com (free tier)       |
