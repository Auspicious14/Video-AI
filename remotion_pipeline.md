# VideoAI.ng — Motion Design Pipeline (Remotion)

Programmatic motion design videos, rendered server-side with Remotion.
Gemini 2.5 Flash generates the design brief; Remotion renders the MP4.

---

## Architecture

```
User Request
    │
    ▼
POST /generate/motion-design          POST /generate/motion-design/flyer
(topic + style + brand color)         (image upload — flyer/graphic)
    │                                       │
    └─────────────────┬─────────────────────┘
                      ▼
           services/motion_brief.py
           ┌──────────────────────────────────────────┐
           │ Gemini 2.5 Flash reads topic/flyer image │
           │ Returns structured DesignBrief JSON       │
           │                                          │
           │ Fields: title, subtitle, bodyText,        │
           │   brandColor, accentColor, bgColor,      │
           │   stats[], listItems[], style, fonts...  │
           └──────────────────────────────────────────┘
                      │
                      ▼
           services/pipeline_motion_design.py
           ┌──────────────────────────────────────────┐
           │ Writes brief to temp JSON file            │
           │ Calls: remotion render <id> --props=...  │
           │ Monitors progress, handles timeout        │
           └──────────────────────────────────────────┘
                      │
                      ▼
           remotion-templates/
           ┌──────────────────────────────────────────┐
           │  MinimalVideo      — quote cards, flyers  │
           │  BoldVideo         — brand intros         │
           │  GlassmorphismVideo — stats/data reveals  │
           │  NeonVideo         — listicles, tip lists │
           └──────────────────────────────────────────┘
                      │
                      ▼
                   MP4 output
```

---

## Templates

| ID                   | Style           | Best For                                            | Key Feature                                          |
| -------------------- | --------------- | --------------------------------------------------- | ---------------------------------------------------- |
| `MinimalVideo`       | `minimal`       | Quote cards, flyer-to-motion, elegant announcements | Animated accent line, fade-slide typography          |
| `BoldVideo`          | `bold`          | Brand intros, product launches, campaign reveals    | Word-by-word kinetic title reveal, kinetic circles   |
| `GlassmorphismVideo` | `glassmorphism` | Stats, KPIs, business metrics                       | Frosted glass cards, count-up animation, aurora orbs |
| `NeonVideo`          | `neon`          | Tip lists, how-tos, listicles                       | Neon-glow numbered items, staggered slide-in         |

All templates support: **9:16** (TikTok/Reels), **16:9** (YouTube), **1:1** (Square)

---

## Setup

```bash
# One-time setup
bash setup_remotion.sh

# What it does:
# 1. Checks Node.js (requires 18+)
# 2. npm install -g remotion @remotion/cli
# 3. npm install in remotion-templates/
# 4. Runs a test render (5 frames) to verify Chromium works
```

**Chromium requirement:** Remotion uses headless Chrome to render. On Ubuntu servers:

```bash
sudo apt install -y chromium-browser
# or
sudo apt install -y google-chrome-stable
```

---

## API

### Topic → Motion Design

```http
POST /generate/motion-design
Content-Type: application/json

{
  "user_email": "user@example.com",
  "topic": "5 tips to grow your Instagram in Nigeria",
  "style": "neon",
  "duration": 20,
  "aspect_ratio": "9:16",
  "brand_name": "GrowthNG",
  "brand_color": "#F4A931"
}
```

### Flyer Image → Motion Design

```http
POST /generate/motion-design/flyer
Content-Type: multipart/form-data

user_email=user@example.com
style=auto
aspect_ratio=9:16
duration=15
[flyer: <image file>]
```

`style=auto` → Gemini picks the best template based on the flyer's visual language.

### Poll job status

```http
GET /generate/jobs/{job_id}

→ {
    "status": "rendering",
    "progress": 65,
    "status_detail": "Remotion is rendering bold template…"
  }

→ {
    "status": "done",
    "video_url": "/outputs/abc123_motion.mp4",
    "caption": "5 Tips to Grow on Instagram...",
    "progress": 100
  }
```

---

## DesignBrief Schema

Gemini generates this JSON and Python passes it to Remotion via `--props`.

```typescript
interface DesignBrief {
  // Template selection
  style: "minimal" | "bold" | "glassmorphism" | "neon";
  aspectRatio: "9:16" | "16:9" | "1:1";
  durationSeconds: number; // 10–30

  // Brand identity
  brandName?: string;
  brandColor: string; // hex e.g. "#F4A931"
  accentColor: string; // contrasting hex
  bgColor: string; // background hex
  textColor: string; // primary text hex

  // Core copy
  title: string; // max ~7 words — the headline
  subtitle?: string;
  bodyText?: string; // longer text (quote cards, flyers)
  tagline?: string; // brand intro line
  cta?: string; // call-to-action

  // Glassmorphism: data
  stats?: {
    label: string;
    value: string;
    prefix?: string; // e.g. "₦"
    suffix?: string; // e.g. "%", "K"
    numericValue: number; // raw number for count-up
  }[];

  // Neon: list
  listItems?: {
    index: number; // 1-based
    headline: string;
    body?: string;
    emoji?: string;
  }[];

  // Style
  animationSpeed: "slow" | "normal" | "fast";
  fontPairing: "syne_dmsans" | "inter" | "playfair_inter";

  // Source metadata
  sourceType: "prompt" | "flyer";
  flyerDescription?: string;
}
```

---

## File Map

```
remotion-templates/
  package.json                    — npm project config
  tsconfig.json                   — TypeScript config
  src/
    index.ts                      — Remotion entry point (registerRoot)
    Root.tsx                      — All four Composition registrations
    types/
      index.ts                    — DesignBrief type + DIMENSIONS + FPS
    components/
      shared.tsx                  — Animation hooks + shared components
    templates/
      Minimal.tsx                 — Quote cards / flyer-to-motion
      Bold.tsx                    — Brand intros
      Glassmorphism.tsx           — Stats / data reveals
      Neon.tsx                    — Listicles / tip lists

backend/
  services/
    motion_brief.py               — Gemini brief generator (topic + flyer)
    pipeline_motion_design.py     — Full pipeline orchestrator
  routers/
    motion_design_routes.py       — Route snippets to add to videos.py
  models_motion_design_patch.py   — MotionDesignRequest patch (add aspect_ratio)

setup_remotion.sh                 — One-time setup script
```

---

## Render Times (approximate)

| Duration | Style                      | Expected Render Time |
| -------- | -------------------------- | -------------------- |
| 10s      | Any                        | 30–60s               |
| 15s      | Any                        | 45–90s               |
| 20s      | Stats/Neon (more elements) | 60–120s              |
| 30s      | Any                        | 90–180s              |

First render is slower (Chrome startup + font downloads). Subsequent renders are faster.

---

## Troubleshooting

**"remotion: command not found"**

```bash
npm install -g remotion @remotion/cli
```

**"Cannot find Chromium"**

```bash
# Ubuntu
sudo apt install -y chromium-browser

# Or let Remotion download its own:
npx remotion browser ensure
```

**Render times out (>5 min)**

- Reduce `--concurrency` (already set to 1)
- Check server RAM (Remotion needs ~1GB free)
- Consider upgrading to a larger VPS for production

**Gemini returns invalid JSON**

- Check `GEMINI_API_KEY` in your `.env`
- The pipeline will raise a clear error with the raw Gemini output
