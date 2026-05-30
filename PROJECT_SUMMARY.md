# VideoAI.ng Project Technical Summary

## Project Overview
VideoAI.ng is a hybrid AI video generation platform designed to create various types of videos including TikTok clips, awareness videos, motion graphics, talking avatars, and true AI-generated videos.

---

## Architecture
The project uses a 3-layer hybrid architecture:

### Layer A: Deterministic FFmpeg Composition (Always Works)
- **Purpose**: Fallback video composition that guarantees a working output
- **Implementation**: FFmpeg-based rendering with Ken Burns (zoompan) effects
- **Features**: Text overlays, audio muxing, aspect ratio handling
- **File**: `services/renderer.py`

### Layer B: AI Asset Generation
- **Script Generation**: Google Gemini (via `google-genai`)
- **Audio Generation**: gTTS (free text-to-speech), optionally ElevenLabs didnt work
- **Image Generation**: FLUX.1-schnell via Hugging Face Inference (works but needs something much better)
- **Files**:
  - `services/script.py`
  - `services/audio.py`
  - `services/images.py`

### Layer C: AI Motion Enhancement (Optional)
- **Text-to-Video**: Wan2.2-TI2V-5B via Hugging Face Inference Providers (fal-ai, replicate)
- **Image-to-Video**: Stable Video Diffusion (SVD)
- **Avatar Animation**: Wav2Lip (local or via Gradio Spaces)
- **Files**:
  - `services/ai_motion.py`
  - `services/avatar.py`
  - `services/pipeline_ai_video.py`
  - `services/pipeline_avatar.py`

---

## Core Modules & Pipelines

### Pipeline Types
1. **TikTok Pipeline** (`services/pipeline_hybrid.py`):
   - Script → Audio → Images → FFmpeg composition
   - Entry point: `/generate/tiktok`

2. **AI Video Pipeline** (`services/pipeline_ai_video.py`):
   - Script → Audio → Images → AI video clips (Wan2.2) → Composition
   - Fallback to Ken Burns for failed clips
   - Entry point: `/generate/ai-video`

3. **Avatar Pipeline** (`services/pipeline_avatar.py`):
   - Script → Audio → Face (FLUX or user upload) → Wav2Lip animation → Composition
   - Entry point: `/generate/avatar`

4. **Motion Design Pipeline** (`services/pipeline_motion_design.py`):
   - Topic → Design brief (Gemini) → Remotion render
   - Entry point: `/generate/motion-design`

5. **Still-to-Motion Pipeline** (`services/pipeline_still.py`):
   - Upload image → Ken Burns animation
   - Entry point: `/generate/still-to-motion`

### Cinematic Reasoning Engine (Core Directory)
The project includes an advanced 10-phase cinematic AI system:

| Phase | Module | Purpose | Entry Point |
|-------|--------|---------|-------------|
| 1 | Scene Intent | Convert user request to structured scene intent | `core/scene_intent/service.py` |
| 2 | Shot Planner | Decompose scenes into camera shots and performances | `core/shot_planner/service.py` |
| 3 | Cinematic State | Persist and manage cinematic state across pipeline | `core/cinematic_state/service.py` |
| 4 | Render Orchestrator | Coordinate rendering across different backends | `core/render_orchestrator/service.py` |
| 5 | Quality Intelligence | Validate continuity, emotional coherence, cinematic quality | `core/quality_intelligence/service.py` |
| 6 | Memory Engine | Character and world memory for continuity | `core/memory_engine/service.py` |
| 7 | Agentic Director | Multi-agent critique and refinement system | `core/agentic_director/service.py` |
| 8 | Performance & Dialogue | Generate synchronized character performances | `core/performance_dialogue_engine/service.py` |
| 9 | Render Scheduler | Dependency-aware job scheduling and fallback routing | `core/render_scheduler/service.py` |
| 10 | Observability Engine | System introspection, metrics, and auto-tuning | `core/observability_engine/service.py` |

---

## Technologies Used
| Category | Tools/Libraries |
|----------|-----------------|
| Backend Framework | FastAPI, Uvicorn |
| AI Scripting | google-genai (Gemini) |
| AI Images | huggingface_hub, FLUX.1-schnell, Pillow |
| AI Audio | gTTS, optionally ElevenLabs |
| AI Video | Wan2.2-TI2V-5B, Stable Video Diffusion |
| Avatar Lip Sync | Wav2Lip, gradio_client |
| Video Rendering | FFmpeg (native via subprocess) |
| Motion Design | Remotion (planned) |
| Payments | Paystack API |
| Storage | In-memory (with DB fallback ready) |

---

## What Didn't Work / Challenges Faced

### 1. Remotion
- **Status**: Abandoned / On Hold
- **Reason**: High resource requirements, long render times, and complex setup
- **Alternatives**: FFmpeg-based motion design with text overlays and animations
- **Files**: `remotion-templates/`, `remotion_pipeline.md`

### 2. Wav2Lip (Gradio Spaces)
- **Status**: Fallback to local execution
- **Reason**: Rate limiting, quota limits, and inconsistent availability of public Gradio Spaces
- **Solution**: Local Wav2Lip installation with checkpoint
- **Files**: `wav2lip/`, `services/avatar.py`

### 3. Wan2.1-T2V-14B (Legacy HF API)
- **Status**: Deprecated
- **Reason**: HF Inference API returned 410 Gone for all video models; migrated to Inference Providers system
- **Solution**: Wan2.2-TI2V-5B via fal-ai and replicate providers
- **File**: `services/pipeline_ai_video.py`

---

## Payment & Credits System
- **Payment Processor**: Paystack (Naira)
- **Webhook Handling**: `/payments/webhook` endpoint
- **Credit Storage**: In-memory dict (with SQLite/Postgres ready for production)
- **Credit Endpoints**:
  - `GET /credits/{email}`: Check credit balance
  - Credit deducted on job creation; refunded on failure

---

## Frontend
- **Technology**: Vanilla HTML/CSS/JavaScript
- **Deployment**: Vercel, Netlify, or GitHub Pages
- **Features**: Job status polling, video preview, credit display, payment flow

---

---

# AI Video Generation Expectations

## Vision
The goal is to generate **true AI videos** — not just stitched images with subtitles and voiceover. The videos should have characters moving, talking, and showing emotions like real-world footage.

## Key Requirements

### 1. Character Movement & Animation
- **Full-body movement**: Characters should walk, gesture, and interact with their environment naturally
- **Facial expressions**: Micro-expressions that match emotional context (smiling, frowning, surprise, etc.)
- **Eye movement**: Natural eye contact, blinks, and gaze direction
- **Body language**: Posture, hand movements, and gestures that align with dialogue

### 2. Lip Sync & Dialogue
- **Accurate lip sync**: Phoneme-level alignment between audio and lip movements
- **Natural speech patterns**: Pauses, breathing, and speech cadence that feel human
- **Emotional delivery**: Tone and facial expressions that match the emotional content of dialogue

### 3. Cinematic Quality
- **Camera movement**: Smooth pans, tilts, dollies, and handheld shots where appropriate
- **Lighting**: Cinematic lighting that matches the scene's mood and time of day
- **Continuity**: Visual consistency across shots (lighting, costumes, props, environment)
- **Pacing**: Rhythmic editing that builds tension and emotional arcs

### 4. Environmental Realism
- **Background motion**: Moving elements in the environment (wind, water, traffic, etc.)
- **Depth of field**: Natural focus and bokeh effects
- **Color grading**: Consistent color palette that enhances the emotional tone
- **Sound design**: Ambient sounds, foley, and spatial audio that immerse the viewer

### 5. Emotional Coherence
- **Emotional arc**: Stories should follow a setup → escalation → resolution pattern
- **Character consistency**: Personalities, behaviors, and visual appearance should remain consistent
- **Subtlety**: Restrained, realistic emotional delivery rather than over-the-top expressions

## Technical Implementation Path

### Short-term (Current)
- Leverage Wan2.2-TI2V-5B for AI video clips
- Improve Wav2Lip for better lip sync
- Enhance FFmpeg composition with smoother transitions
- Implement Phase 1-5 cinematic modules

### Medium-term
- Integrate Phase 6-10 cinematic reasoning and agentic refinement
- Add character identity and world memory for continuity
- Implement quality intelligence validation
- Explore better text-to-video models (CogVideoX, Sora alternatives)

### Long-term
- Full end-to-end AI video generation from text prompt
- Photorealistic characters with natural movement and emotion
- Multi-scene narratives with complex character interactions
- Self-optimizing rendering pipeline with cinematic observability
