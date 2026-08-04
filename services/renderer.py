"""
services/renderer.py  —  Deterministic Composition Engine (Layer A)
═══════════════════════════════════════════════════════════════════════════════

Root cause of shake / vibration (now eliminated):
  1. FPS=25 — FFmpeg zoompan's per-frame x/y is recalculated each call with
     floating-point drift.  Fixed: FPS=30, ALL positions are trunc()-wrapped.
  2. random.choice() for effects — non-deterministic per run.  Fixed: caller
     supplies effect_index; effects are chosen by scene position, not RNG.
  3. zoompan doesn't emit an FPS-locked stream unless fps= is set AND the
     output -r flag is also set.  Fixed: both are always 30.
  4. scale= step was 0.002 (too coarse → visible jitter).  Fixed: 0.0006.
  5. x/y expressions in zoompan must use trunc() to stay on integer pixels.
     We also multiply by 1.0 to keep FFmpeg's expression engine happy.

Architecture (Layers A / B / C):
  ┌─ Layer A: Deterministic Composition Engine (this file)
  │   • FFmpeg zoompan / parallax / transitions
  │   • PIL subtitle + overlay compositing
  │   • Fixed 30 fps, configurable aspect ratio (9:16, 16:9, 1:1)
  │
  ├─ Layer B: AI asset generation (images.py / audio.py)
  └─ Layer C: AI motion clips (ai_motion.py) — optional enhancement
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple
# pyrefly: ignore [missing-import]
from PIL import Image, ImageDraw, ImageFont
from config import OUTPUT_DIR

# ─── Master constants ─────────────────────────────────────────────────────────
FPS    = 30          # LOCKED — never change per-call, use this everywhere
W      = 1080        # default output width  (9:16 portrait for TikTok)
H      = 1920        # default output height
SCALE  = 2           # overscan for zoompan (2× avoids black edges)
SW     = W * SCALE   # 2160
SH     = H * SCALE   # 3840
# Max zoom factor (1.5 = 50% zoom-in).  Keep ≤1.5 for quality.
MAX_Z  = 1.5
# Zoom step per frame — tiny value is key to eliminating jitter
ZOOM_STEP = 0.0007


def dimensions_for_aspect_ratio(aspect_ratio: str = "9:16") -> tuple[int, int]:
    """Return render dimensions for supported aspect ratios."""
    if aspect_ratio == "16:9":
        return 1920, 1080
    if aspect_ratio == "1:1":
        return 1080, 1080
    return W, H


# ─── Motion effect presets (deterministic, no randomness) ────────────────────
# All expressions use trunc() to snap to integer pixel coords.
# d = total frames for the clip.  fps= must match FPS constant.

def _render_dims(width: int, height: int) -> tuple[int, int, int, int]:
    return width, height, width * SCALE, height * SCALE


def _zoom_in(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Slow push-in from 1.0× to MAX_Z×."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='if(lte(on,1),1,zoom+{ZOOM_STEP:.4f})':"
        f"x='trunc(iw/2-(iw/zoom/2))':"
        f"y='trunc(ih/2-(ih/zoom/2))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


def _zoom_out(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Pull-back from MAX_Z× to 1.0×."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='if(eq(on,1),{MAX_Z:.1f},max({MAX_Z:.1f}-on*{ZOOM_STEP:.4f},1.0))':"
        f"x='trunc(iw/2-(iw/zoom/2))':"
        f"y='trunc(ih/2-(ih/zoom/2))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


def _pan_right(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Horizontal pan left-to-right at fixed 1.2× zoom."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    travel = f"(iw-iw/1.2)"
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='1.2':"
        f"x='trunc({travel}*(on-1)/({d}-1))':"
        f"y='trunc(ih/2-(ih/1.2/2))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


def _pan_left(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Horizontal pan right-to-left at fixed 1.2× zoom."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    travel = f"(iw-iw/1.2)"
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='1.2':"
        f"x='trunc({travel}*(1-(on-1)/({d}-1)))':"
        f"y='trunc(ih/2-(ih/1.2/2))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


def _tilt_up(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Vertical pan top-to-bottom at fixed 1.2× zoom."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    travel = f"(ih-ih/1.2)"
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='1.2':"
        f"x='trunc(iw/2-(iw/1.2/2))':"
        f"y='trunc({travel}*(on-1)/({d}-1))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


def _tilt_down(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Vertical pan bottom-to-top at fixed 1.2× zoom."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    travel = f"(ih-ih/1.2)"
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='1.2':"
        f"x='trunc(iw/2-(iw/1.2/2))':"
        f"y='trunc({travel}*(1-(on-1)/({d}-1)))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


def _diagonal_pan_right_up(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Diagonal pan right-up at fixed 1.2× zoom."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    travel_x = f"(iw-iw/1.2)"
    travel_y = f"(ih-ih/1.2)"
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='1.2':"
        f"x='trunc({travel_x}*(on-1)/({d}-1))':"
        f"y='trunc({travel_y}*(1-(on-1)/({d}-1)))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


def _diagonal_pan_left_down(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Diagonal pan left-down at fixed 1.2× zoom."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    travel_x = f"(iw-iw/1.2)"
    travel_y = f"(ih-ih/1.2)"
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='1.2':"
        f"x='trunc({travel_x}*(1-(on-1)/({d}-1)))':"
        f"y='trunc({travel_y}*(on-1)/({d}-1))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


def _static(duration: float, fps: int = FPS, width: int = W, height: int = H) -> str:
    """Static frame — no motion at all (guaranteed stable)."""
    d = max(1, int(duration * fps))
    w, h, sw, sh = _render_dims(width, height)
    return (
        f"scale={sw}:{sh},"
        f"zoompan="
        f"z='1.0':"
        f"x='trunc(iw/2-(iw/2))':"
        f"y='trunc(ih/2-(ih/2))':"
        f"d={d}:fps={fps}:s={w}x{h}"
    )


# Ordered list — index is used for DETERMINISTIC selection (no random)
MOTION_EFFECTS: List = [
    _zoom_in,              # 0
    _zoom_out,             # 1
    _pan_right,            # 2
    _pan_left,             # 3
    _tilt_up,              # 4
    _tilt_down,            # 5
    _diagonal_pan_right_up,# 6
    _diagonal_pan_left_down,#7
    _static,               #8  — fall-back for scenes where motion would look bad
]

# Effect name → function map (for StillToMotion / API requests)
EFFECT_MAP = {fn.__name__.lstrip("_"): fn for fn in MOTION_EFFECTS}

# Emotion to effect mapping
EMOTION_EFFECT_MAP = {
    'urgent': _zoom_in,
    'hopeful': _zoom_out,
    'informative': _pan_right,
    'empathetic': _zoom_in,
    'inspiring': _diagonal_pan_right_up
}



# ─── Transition presets ───────────────────────────────────────────────────────
TRANSITIONS = [
    "fade",
]
# Deterministic transition selection: always use smooth crossfade (duration=0.4)
def _pick_transition(scene_index: int) -> str:
    return "fade"



# ─── Font loader ──────────────────────────────────────────────────────────────

def _find_font(size: int) -> ImageFont.FreeTypeFont:
    for path in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ─── Text overlay (PIL) ───────────────────────────────────────────────────────

def create_text_overlay(
    text: str,
    output_path: Path,
    font_size: int = 38,
    width: int = W,
    height: int = H,
    y_pos: int = None,
    color: tuple = (255, 255, 255, 255),
    box_color: tuple = (0, 0, 0, 160),
    max_width_fraction: float = 0.88,
) -> Path:
    """Renders word-wrapped text onto a transparent PNG for FFmpeg overlay."""
    img  = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _find_font(font_size)
    max_w = int(width * max_width_fraction)
    if y_pos is None:
        y_pos = int(height * 0.75)

    words, lines, current = text.split(), [], []
    for word in words:
        test = " ".join(current + [word])
        if draw.textlength(test, font=font) > max_w:
            if current:
                lines.append(" ".join(current))
                current = [word]
            else:
                lines.append(word)
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))

    curr_y = y_pos
    pad = 12
    for line in lines:
        w   = draw.textlength(line, font=font)
        x   = int((width - w) / 2)
        bbox = [x - pad, curr_y - pad, x + w + pad, curr_y + font_size + pad]
        draw.rounded_rectangle(bbox, radius=8, fill=box_color)
        draw.text((x, curr_y), line, font=font, fill=color)
        curr_y += font_size + 14

    img.save(output_path, format="PNG")
    return output_path


# ─── Scene subtitle overlay ───────────────────────────────────────────────────

def create_subtitle_overlay(
    lines: List[Tuple[str, float, float]],  # [(text, start_t, end_t), ...]
    video_path: Path,
    output_path: Path,
    font_size: int = 46,
    fps: int = FPS,
    width: int = W,
    height: int = H,
) -> Path:
    """
    Burns subtitle cards into a video using PIL + FFmpeg overlay filter.
    Each line appears at start_t and disappears at end_t.
    Falls back gracefully if FFmpeg drawtext is unavailable.
    """
    if not lines:
        return video_path

    # Build a Python-drawn subtitle overlay image per segment using
    # FFmpeg's overlay with enable= timing expressions.
    # This avoids drawtext font path issues across OS.
    overlays_args: List[str] = []
    inputs: List[str] = ["-i", str(video_path)]
    filter_parts: List[str] = []
    prev = "0:v"

    tmp_dir = output_path.parent

    for idx, (text, t_start, t_end) in enumerate(lines):
        overlay_path = tmp_dir / f"sub_{idx:04d}.png"
        create_text_overlay(
            text, overlay_path,
            font_size=font_size,
            width=width,
            height=height,
            y_pos=height - max(220, int(height * 0.17)),
            color=(255, 255, 255, 255),
            box_color=(0, 0, 0, 200),
        )
        inputs += ["-i", str(overlay_path)]
        out_label = f"sv{idx}"
        # input index = idx + 1 (0 is the video)
        filter_parts.append(
            f"[{prev}][{idx + 1}:v]overlay="
            f"enable='between(t,{t_start:.3f},{t_end:.3f})'[{out_label}]"
        )
        prev = out_label

    filter_complex = ";".join(filter_parts)
    cmd = (
        ["ffmpeg", "-y"]
        + inputs
        + [
            "-filter_complex", filter_complex,
            "-map", f"[{prev}]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            str(output_path),
        ]
    )
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"[renderer] Subtitle overlay failed, using raw video: {result.stderr.decode()[-300:]}")
        return video_path
    return output_path


# ─── Per-scene clip builder ───────────────────────────────────────────────────

def build_scene_clip(
    img_path: Path,
    duration: float,
    output_path: Path,
    effect_fn=None,
    fps: int = FPS,
    ai_clip_path: Optional[Path] = None,
    width: int = W,
    height: int = H,
) -> None:
    """
    Builds a single scene clip, either from:
      A) An AI-generated video clip (Layer C) — preferred if provided
      B) A still image with a deterministic motion effect (Layer A fallback)

    The output is always W×H @ fps, yuv420p.
    """
    # Layer C: use the AI-generated clip if available and valid
    if ai_clip_path and ai_clip_path.exists() and ai_clip_path.stat().st_size > 10_000:
        _normalize_clip(ai_clip_path, output_path, duration, fps, width=width, height=height)
        return

    # Layer A: deterministic Ken Burns effect
    if effect_fn is None:
        effect_fn = _zoom_in  # safe deterministic default

    vf = effect_fn(duration, fps, width, height)

    result = subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-framerate", str(fps),   # input framerate hint
        "-i", str(img_path),
        "-vf", vf,
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-r", str(fps),           # output framerate — must match fps= in zoompan
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        str(output_path),
    ], capture_output=True)

    if result.returncode != 0:
        err = result.stderr.decode()[-500:]
        raise ValueError(f"Scene clip failed ({img_path.name}): {err}")


def _normalize_clip(src, dst, duration, fps, width=W, height=H):
    """Re-encodes a clip to exact W×H @ fps, looping if the source is shorter
    than the allocated beat duration. Real stock clips are very often shorter
    than their assigned beat — without -stream_loop, ffmpeg just ends early
    once the source runs out, silently truncating that beat (and the whole
    chained video) well below its planned length."""
    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma=20,setsar=1[bg];"
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )
    result = subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(src),
        "-filter_complex", filter_complex,
        "-t", str(duration),
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        str(dst),
    ], capture_output=True)
    if result.returncode != 0:
        raise ValueError(f"Clip normalization failed: {result.stderr.decode()[-300:]}")

# ─── Final video assembler ────────────────────────────────────────────────────

def build_final_video(
    scene_clips: List[Tuple[Path, float]],   # [(clip_path, duration), ...]
    audio_path: Path,
    hook_text: str,
    cta_text: str,
    actual_duration: float,
    output_path: Path,
    tmp: Path,
    fps: int = FPS,
    transition_duration: float = 0.4,
    subtitle_lines: Optional[List[Tuple[str, float, float]]] = None,
    bgm_path: Optional[Path] = None,
    width: int = W,
    height: int = H,
) -> Path:
    """
    Full deterministic composition:
      1. Chain scene clips with xfade transitions
      2. Composite hook overlay (first 3 s) and CTA overlay (last 5 s)
      3. Burn subtitles (optional)
      4. Mix audio
      5. Write final MP4
    """
    # 1. Chain clips
    if len(scene_clips) == 1:
        chained = scene_clips[0][0]
    else:
        chained = _chain_with_transitions(scene_clips, tmp, fps, transition_duration)

    # 2. Text overlays
    hook_overlay = tmp / "hook.png"
    cta_overlay  = tmp / "cta.png"

    hook_words = hook_text.split()
    if len(hook_words) > 20:
        hook_text = " ".join(hook_words[:20]) + "…"

    create_text_overlay(
        hook_text, hook_overlay,
        font_size=max(34, int(width * 0.037)),
        width=width,
        height=height,
        y_pos=max(52, int(height * 0.055)),
        color=(255, 255, 255, 255), box_color=(0, 0, 0, 175),
    )
    create_text_overlay(
        cta_text, cta_overlay,
        font_size=max(30, int(width * 0.032)),
        width=width,
        height=height,
        y_pos=height - max(160, int(height * 0.10)),
        color=(255, 220, 50, 255), box_color=(0, 0, 0, 185),
    )

    cta_start = max(0.0, actual_duration - 5.0)
    overlaid   = tmp / "overlaid.mp4"
    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(chained),
        "-i", str(hook_overlay),
        "-i", str(cta_overlay),
        "-filter_complex",
        f"[0:v][1:v]overlay=enable='between(t,0,3)'[v1];"
        f"[v1][2:v]overlay=enable='between(t,{cta_start:.3f},{actual_duration:.3f})'[vout]",
        "-map", "[vout]",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        str(overlaid),
    ], capture_output=True)

    if result.returncode != 0:
        raise ValueError(
            f"Overlay composite failed: {result.stderr.decode()[-600:]}"
        )

    # 3. Subtitles (optional)
    subtitled = overlaid
    if subtitle_lines:
        sub_out = tmp / "subtitled.mp4"
        subtitled = create_subtitle_overlay(
            subtitle_lines, overlaid, sub_out, fps=fps, width=width, height=height
        )

    # 4. Audio mux
    cmd = ["ffmpeg", "-y", "-i", str(subtitled), "-i", str(audio_path)]
    filter_parts = []
    if bgm_path and bgm_path.exists() and bgm_path.stat().st_size > 100:
        cmd += ["-i", str(bgm_path)]
        filter_parts.append("[1:a]volume=1.0[a1];[2:a]volume=-18dB[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        a_input = "[aout]"
    else:
        filter_parts.append("[1:a]anull[aout]")
        a_input = "[aout]"
    filter_parts.append(f"{a_input}loudnorm=I=-16:TP=-1.5:LRA=11[a_norm]")
    filter_complex = ";".join(filter_parts)

    result = subprocess.run(
        cmd + [
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[a_norm]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path),
        ],
        capture_output=True,
    )

    if result.returncode != 0:
        raise ValueError(
            f"Audio mux failed: {result.stderr.decode()[-600:]}"
        )

    return output_path


# ─── TikTok / Hybrid pipeline renderer ───────────────────────────────────────

async def render_video(
    audio_path: Path,
    image_paths: List[Tuple[Path, float]],  # [(img_path, duration), ...]
    script: dict,
    job_id: str,
    actual_duration: float,
    ai_clip_paths: Optional[List[Optional[Path]]] = None,  # Layer C clips
    subtitle_lines: Optional[List[Tuple[str, float, float]]] = None,
    bgm_path: Optional[Path] = None,
    aspect_ratio: str = "9:16",
) -> Path:
    """
    Main render entry-point for the hybrid pipeline.

    Effect selection is DETERMINISTIC (scene index % len(MOTION_EFFECTS)).
    AI clips are used when available; still images animate as fallback.
    """
    output_path = OUTPUT_DIR / f"{job_id}_final.mp4"
    fps         = FPS
    width, height = dimensions_for_aspect_ratio(aspect_ratio)

    # Sanity checks
    if not audio_path.exists() or audio_path.stat().st_size < 100:
        raise ValueError(f"Audio file missing/corrupt: {audio_path.name}")
    for img_path, _ in image_paths:
        if not img_path.exists() or img_path.stat().st_size < 500:
            raise ValueError(f"Image file missing/corrupt: {img_path.name}")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)

        scene_clips: List[Tuple[Path, float]] = []
        n = len(image_paths)

        for i, (img_path, duration) in enumerate(image_paths):
            # Deterministic effect selection: no randomness
            effect_fn  = MOTION_EFFECTS[i % len(MOTION_EFFECTS)]
            ai_clip    = (ai_clip_paths[i] if ai_clip_paths and i < len(ai_clip_paths)
                          else None)
            clip_path  = tmp / f"clip_{i:02d}.mp4"

            build_scene_clip(
                img_path, duration, clip_path,
                effect_fn=effect_fn, fps=fps,
                ai_clip_path=ai_clip,
                width=width,
                height=height,
            )
            scene_clips.append((clip_path, duration))

        build_final_video(
            scene_clips=scene_clips,
            audio_path=audio_path,
            hook_text=script.get("hook", ""),
            cta_text=script.get("cta", ""),
            actual_duration=actual_duration,
            output_path=output_path,
            tmp=tmp,
            fps=fps,
            transition_duration=0.4,
            subtitle_lines=subtitle_lines,
            bgm_path=bgm_path,
            width=width,
            height=height,
        )

    return output_path


# ─── Still Image → Motion renderer ───────────────────────────────────────────

async def render_still_to_motion(
    image_path: Path,
    audio_path: Path,
    hook_text: str,
    cta_text: str,
    actual_duration: float,
    job_id: str,
    effect_fn=None,
    aspect_ratio: str = "9:16",
) -> Path:
    """
    Single-image Ken Burns animation pipeline.
    Uses _zoom_in by default if no effect_fn is specified.
    """
    output_path = OUTPUT_DIR / f"{job_id}_final.mp4"
    fps         = FPS
    width, height = dimensions_for_aspect_ratio(aspect_ratio)

    if effect_fn is None:
        effect_fn = _zoom_in  # deterministic default

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        clip_path = tmp / "clip_00.mp4"
        build_scene_clip(
            image_path,
            actual_duration,
            clip_path,
            effect_fn=effect_fn,
            fps=fps,
            width=width,
            height=height,
        )

        build_final_video(
            scene_clips=[(clip_path, actual_duration)],
            audio_path=audio_path,
            hook_text=hook_text,
            cta_text=cta_text,
            actual_duration=actual_duration,
            output_path=output_path,
            tmp=tmp,
            fps=fps,
            width=width,
            height=height,
        )

    return output_path


# ─── Private helpers ──────────────────────────────────────────────────────────

def _chain_with_transitions(
    scene_clips: List[Tuple[Path, float]],
    tmp: Path,
    fps: int,
    transition_duration: float,
) -> Path:
    """
    Chains multiple clips using xfade transitions.
    Transition selection is DETERMINISTIC (by scene position).
    Falls back to simple concat if xfade is unavailable.
    """
    inputs: List[str] = []
    for clip_path, _ in scene_clips:
        inputs += ["-i", str(clip_path)]

    n             = len(scene_clips)
    chain_filter  = ""
    prev_label    = "0:v"
    offset        = 0.0

    for i in range(1, n):
        transition = _pick_transition(i)
        offset    += scene_clips[i - 1][1] - transition_duration
        offset     = max(0.0, offset)
        out_label  = f"v{i}"
        chain_filter += (
            f"[{prev_label}][{i}:v]xfade=transition={transition}:"
            f"duration={transition_duration}:offset={offset:.3f}[{out_label}];"
        )
        prev_label = out_label

    chain_filter = chain_filter.rstrip(";")
    output_path  = tmp / "chained.mp4"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", chain_filter,
        "-map", f"[{prev_label}]",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print("[renderer] xfade unavailable, falling back to concat")
        return _chain_with_concat(scene_clips, tmp, fps)

    return output_path


def _chain_with_concat(
    scene_clips: List[Tuple[Path, float]],
    tmp: Path,
    fps: int,
) -> Path:
    """Hard-cut concat fallback when xfade is not available."""
    # Re-encode all clips to ensure uniform codec/fps before concat
    concat_file = tmp / "concat.txt"
    lines = [f"file '{clip}'\n" for clip, _ in scene_clips]
    concat_file.write_text("".join(lines))

    output_path = tmp / "chained.mp4"
    result = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-preset", "slow",
        "-crf", "18",
        str(output_path),
    ], capture_output=True)

    if result.returncode != 0:
        raise ValueError(
            f"Concat fallback failed: {result.stderr.decode()[-400:]}"
        )
    return output_path

    """
ADD THIS TO THE BOTTOM OF services/renderer.py
═══════════════════════════════════════════════════════════════════════════════

Paste everything below the last line of renderer.py.
It uses all the same constants (FPS, W, H) already defined there.
No new imports needed — all are already at the top of renderer.py.
"""


async def render_avatar_video(
    avatar_clip: Path,                          # animated talking head MP4
    audio_path: Path,                           # clean TTS audio
    image_paths: list,                          # B-roll [(Path, duration), ...]
    script: dict,
    job_id: str,
    actual_duration: float,
    aspect_ratio: str = "9:16",
) -> Path:
    """
    Composes the final avatar video:
      1. Normalise avatar clip to W×H @ FPS
      2. Replace audio with clean TTS track (avatar clip audio is discarded)
      3. Add hook overlay (first 3s) and CTA overlay (last 5s)
      4. Write final MP4

    B-roll images are generated but not composited yet (future: pip layout).
    They are kept for potential future use without re-generation cost.
    """
    output_path = OUTPUT_DIR / f"{job_id}_final.mp4"
    width, height = dimensions_for_aspect_ratio(aspect_ratio)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)

        # ── Step 1: normalise avatar clip ─────────────────────────────────────
        normalised = tmp / "avatar_normalised.mp4"
        _normalize_clip(avatar_clip, normalised, actual_duration, FPS, width=width, height=height)

        # ── Step 2: text overlays ─────────────────────────────────────────────
        hook_overlay = tmp / "hook.png"
        cta_overlay  = tmp / "cta.png"

        create_text_overlay(
            script.get("hook", ""),
            hook_overlay,
            font_size=max(34, int(width * 0.037)),
            width=width,
            height=height,
            y_pos=max(52, int(height * 0.055)),
            color=(255, 255, 255, 255),
            box_color=(0, 0, 0, 175),
        )
        create_text_overlay(
            script.get("cta", ""),
            cta_overlay,
            font_size=max(30, int(width * 0.032)),
            width=width,
            height=height,
            y_pos=height - max(160, int(height * 0.10)),
            color=(255, 220, 50, 255),
            box_color=(0, 0, 0, 185),
        )

        cta_start = max(0.0, actual_duration - 5.0)

        # ── Step 3: composite overlays + replace audio ─────────────────────────
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(normalised),
            "-i", str(hook_overlay),
            "-i", str(cta_overlay),
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:v][1:v]overlay=enable='between(t,0,3)'[v1];"
            f"[v1][2:v]overlay=enable='between(t,{cta_start:.3f},{actual_duration:.3f})'[vout]",
            "-map", "[vout]",
            "-map", "3:a",              # use clean TTS audio, discard avatar audio
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            str(output_path),
        ], capture_output=True)

        if result.returncode != 0:
            raise ValueError(
                f"Avatar render failed: {result.stderr.decode()[-600:]}"
            )

    return output_path

def create_fallback_frame(text: str, output_path: Path, width: int, height: int) -> Path:
    """Solid-background Layer A fallback — guarantees a beat always has
    something to render, even when every real/AI asset source fails."""

    img = Image.new("RGB", (width, height), (26, 26, 46))
    draw = ImageDraw.Draw(img)
    font = _find_font(48)
    words, lines, current = text.split(), [], []
    max_w = int(width * 0.8)
    for word in words:
        test = " ".join(current + [word])
        if draw.textlength(test, font=font) > max_w:
            lines.append(" ".join(current)) if current else lines.append(word)
            current = [] if current else current
            if not current:
                current = [word] if lines and lines[-1] != word else []
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    y = (height - len(lines) * 60) // 2
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((width - w) / 2, y), line, font=font, fill=(255, 255, 255))
        y += 60
    img.save(output_path)
    return output_path