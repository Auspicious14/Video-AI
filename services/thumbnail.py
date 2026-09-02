"""services/thumbnail.py — Renders an actual clickable YouTube thumbnail,
distinct from in-video text overlays. Separate 1280x720 image, uploaded
independently on YouTube — never part of the rendered video itself."""

from click import prompt
from services.ai.schemas import ThumbnailStrategyResult
from pathlib import Path
# pyrefly: ignore [missing-import]
from PIL import Image, ImageDraw, ImageEnhance
from services.renderer import _find_font
import logging

logger = logging.getLogger(__name__)

def _punch_up(img: Image.Image) -> Image.Image:
    """Thumbnails read as dull and flat at small mobile sizes unless
    pushed harder than a normal video frame — standard thumbnail-editing
    trick, not optional polish."""
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Color(img).enhance(1.25)
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    return img


# def create_thumbnail(
#     background_path: Path,
#     text: str,
#     output_path: Path,
#     width: int = 1280,
#     height: int = 720,
#     font_size: int = 110,
#     accent_color: tuple = (255, 210, 0, 255),
# ) -> Path:
#     img = Image.open(background_path).convert("RGB")
#     img_ratio, target_ratio = img.width / img.height, width / height
#     if img_ratio > target_ratio:
#         new_h = height
#         new_w = int(height * img_ratio)
#     else:
#         new_w = width
#         new_h = int(width / img_ratio)
#     img = img.resize((new_w, new_h))
#     left, top = (new_w - width) // 2, (new_h - height) // 2
#     img = _punch_up(img.crop((left, top, left + width, top + height)))

#     img = img.convert("RGBA")
#     draw = ImageDraw.Draw(img)
#     font = _find_font(font_size)

#     words = text.split()
#     if len(words) > 4:
#         text = " ".join(words[:4])  # thumbnail text: 2-5 words, phone-readable

#     max_w = int(width * 0.86)
#     lines, current = [], []
#     for word in text.split():
#         test = " ".join(current + [word])
#         if draw.textlength(test, font=font) > max_w and current:
#             lines.append(" ".join(current))
#             current = [word]
#         else:
#             current.append(word)
#     if current:
#         lines.append(" ".join(current))

#     line_height = font_size + 14
#     y = height - (len(lines) * line_height) - 60

#     for line in lines:
#         w = draw.textlength(line, font=font)
#         x = (width - w) / 2
#         # Heavy outline — the single biggest legibility factor at
#         # thumbnail size in a crowded feed
#         for dx in range(-6, 7, 2):
#             for dy in range(-6, 7, 2):
#                 draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
#         draw.text((x, y), line, font=font, fill=accent_color)
#         y += line_height

#     img.convert("RGB").save(output_path, format="JPEG", quality=92)
#     return output_path


def create_thumbnail(
    background_path: Path,
    text: str,
    output_path: Path,
    width: int = 1280,
    height: int = 720,
    accent_color=(255, 201, 14, 255),
) -> Path:

    img = Image.open(background_path).convert("RGB")
    img_ratio = img.width / img.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        new_h = height
        new_w = int(height * img_ratio)
    else:
        new_w = width
        new_h = int(width / img_ratio)

    img = img.resize((new_w, new_h))
    left = (new_w - width) // 2
    top = (new_h - height) // 2

    img = img.crop((left, top, left + width, top + height))
    img = _punch_up(img)
    img = img.convert("RGBA")

    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)

    # left gradient

    for x in range(width):
        alpha = int(170 * (1 - x / (width * 0.55)))
        alpha = max(alpha,0)
        draw.line(
            [(x,0),(x,height)],
            fill=(0,0,0,alpha)
        )

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    words = text.split()

    for sep in ("|", "•", "—", "-"):
        if sep in text:
            text = text.split(sep)[0].strip()
            break

    words = text.split()
    if len(words) > 14:
        text = " ".join(words[:14])

    font_size = 92
    font = _find_font(font_size)
    max_width = int(width * 0.42)

    lines = []
    current=[]

    for word in text.split():
        test = " ".join(current + [word])
        if draw.textlength(test, font=font) > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))

    MAX_LINES = 3
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]
        lines[-1] = lines[-1].rstrip() + "…"

    x = 60
    y = height * 0.28
    line_spacing = font_size + 8
    
    for line in lines:
        for dx in range(-5,6):
            for dy in range(-5,6):
                draw.text(
                    (x+dx,y+dy),
                    line,
                    font=font,
                    fill=(0,0,0,255)
                )
        draw.text(
            (x,y),
            line,
            font=font,
            fill=accent_color
        )
        y += line_spacing
    img.convert("RGB").save(
        output_path,
        quality=94
    )
    return output_path


async def render_thumbnail_for_job(
    *,
    job_id: str,
    topic: str,
    thumbnails: "ThumbnailStrategyResult",
    output_dir: Path,
) -> Path | None:
    """
    AI generation from the scored image_prompt is PRIMARY. Real stock photo
    search was pulling topically-wrong images (e.g. a 2020 crash photo for
    a 2008 video) because stock libraries mislabel financial/news imagery,
    and such photos often have real headline text baked into the source
    image — clashing with the intentional text_overlay. Real-photo search
    is now fallback-only, used solely if AI generation fails outright.
    """
    if not thumbnails.concepts:
        return None
    best = thumbnails.concepts[thumbnails.best_index]

    background_path = output_dir / f"{job_id}_thumb_bg.jpg"
    generated_ok = False

    from services.images import get_image_client
    image_client = get_image_client()
    prompt = f"{best.image_prompt}, no text, no words, no captions, no typography, clean photographic composition"
    try:
        await image_client.generate_image(
            prompt=prompt, output_path=str(background_path), width=1280, height=720,
            tier="quality",
        )
        generated_ok = True
    except Exception as exc:
        logger.warning(f"[Thumbnail] AI background generation failed: {exc}")

    if not generated_ok:
        used_real_photo = await _try_real_photo_background(topic, best.concept, background_path)
        if not used_real_photo:
            return None

    output_path = output_dir / f"{job_id}_thumbnail.jpg"
    return create_thumbnail(background_path, best.text_overlay or topic, output_path)

# async def render_thumbnail_for_job(
#     *,
#     job_id: str,
#     topic: str,
#     thumbnails: ThumbnailStrategyResult,
#     output_dir: Path,
# ) -> Path | None:
#     """
#     Turns the best scored thumbnail concept into an actual clickable
#     1280x720 thumbnail — real photo first (same asset pipeline used for
#     in-video visuals), AI-generated as fallback. Same "real asset first"
#     philosophy as everywhere else in this system, not a new paradigm.
#     """
#     if not thumbnails.concepts:
#         return None
#     best = thumbnails.concepts[thumbnails.best_index]

#     background_path = output_dir / f"{job_id}_thumb_bg.jpg"
#     used_real_photo = await _try_real_photo_background(topic, best.concept, background_path)

#     if not used_real_photo:
#         from services.images import get_image_client
#         image_client = get_image_client()
#         prompt = f"""
#             Ultra realistic editorial documentary photograph.

#             {best.image_prompt}

#             Photorealistic.
#             Professional DSLR.
#             Reuters quality.
#             Getty Images quality.
#             Natural lighting.
#             No text.
#             No watermark.
#             No illustration.
#             No painting.
#             No CGI.
#             Subject fills the right side of the frame.
#             Leave clean negative space on the left for headline.
#             High contrast.
#             Emotionally striking.
#             16:9.
#             """
#         try:
#             await image_client.generate_image(
#                 prompt=prompt, output_path=str(background_path), width=1280, height=720,
#             )
#         except Exception as exc:
#             logger.warning(f"[Thumbnail] Background generation failed: {exc}")
#             return None

#     output_path = output_dir / f"{job_id}_thumbnail.jpg"
#     overlay_text = best.text_overlay.strip() if best.text_overlay else topic
#     return create_thumbnail(
#     background_path=background_path,
#     text=overlay_text,
#     output_path=output_path,
# )


async def _try_real_photo_background(topic: str, concept: str, output_path: Path) -> bool:
    """Real photo (press/archival style) before AI generation — real faces
    and real places reliably outperform illustrations for click-through."""
    try:
        from services.ai.media.default_registry import build_registry
        from services.ai.media.asset_types import AssetKind
        from services.ai.media.visual_intent import VisualIntent, ShotType, SubjectType, CameraMotion, Emotion

        registry = build_registry()
        intent = VisualIntent(
            subject=f"{topic} — {concept}"[:160],
            subject_type=SubjectType.OBJECT,
            action="thumbnail-worthy hero shot",
            shot_type=ShotType.MEDIUM,
            motion=CameraMotion.PUSH_IN,
            emotion=Emotion.SERIOUS,
            must_show=[topic],
            search_keywords=[topic],
            preferred_sources=["wikimedia", "google_images"],
            preferred_asset_kind=AssetKind.STOCK_IMAGE,
        )
        for provider in registry.providers_for(AssetKind.STOCK_IMAGE):
            candidates = await provider.search(intent, limit=3)
            if candidates:
                best = max(candidates, key=lambda c: (c.quality or 0) + (c.credibility or 0))
                import requests
                resp = requests.get(best.url, timeout=15)
                resp.raise_for_status()
                output_path.write_bytes(resp.content)
                logger.info(f"[Thumbnail] Using real photo from {best.provider}")
                return True
    except Exception as exc:
        logger.warning(f"[Thumbnail] Real photo search failed, falling back to AI: {exc}")
    return False