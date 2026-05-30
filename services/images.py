import io
import os
import logging
import requests
from pathlib import Path
from typing import Optional
from config import OUTPUT_DIR, GEMINI_API_KEY, HF_API_KEY, FAL_KEY
from google import genai as google_genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)
gemini_client = google_genai.Client(api_key=GEMINI_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER WATERFALL (first success wins):
#
#   1. Google Gemini Imagen 3  — FREE 500 images/day, no credit card
#                                uses your existing GEMINI_API_KEY
#
#   2. HuggingFace FLUX.1-schnell — FREE monthly quota (resets each month)
#                                   uses your existing HF_API_KEY
#
#   3. fal.ai FLUX.1-dev       — PAID last resort (~$0.05/image)
#                                uses your existing FAL_KEY
#
# No new accounts or API keys needed — everything uses what you already have.
# ─────────────────────────────────────────────────────────────────────────────


def enhance_prompt(base_prompt: str, scene_context: str = "", health_mode: bool = False) -> str:
    """Append cinematic suffixes unless the prompt already contains them."""
    if "photorealistic" in base_prompt.lower():
        return base_prompt

    parts = [base_prompt]
    if scene_context:
        parts.append(scene_context)

    parts.extend([
        "photorealistic",
        "sharp focus",
        "cinematic lighting",
        "4K",
        "high detail",
    ])

    if health_mode:
        parts.extend(["professional", "clean", "trustworthy", "warm hopeful atmosphere"])

    return ", ".join(parts)


class ImageGenerationClient:
    """
    Image generation with 3-provider waterfall:
    Gemini Imagen 3 (free 500/day) → HuggingFace FLUX.1-schnell (free monthly) → fal.ai (paid)
    """

    def __init__(
        self,
        gemini_key: Optional[str] = None,
        hf_key: Optional[str] = None,
        fal_key: Optional[str] = None,
    ):
        self.gemini_key = gemini_key or GEMINI_API_KEY
        self.hf_key = hf_key or HF_API_KEY
        self.fal_key = fal_key or FAL_KEY

        if not any([self.gemini_key, self.hf_key, self.fal_key]):
            raise ValueError(
                "At least one of GEMINI_API_KEY, HF_API_KEY, or FAL_KEY must be set."
            )

    # ── Provider 1: Google Gemini Imagen 3 ───────────────────────────────────
    # 500 images/day free. Uses your existing GEMINI_API_KEY.
    # Best quality of the free options — handles Nigerian/African subjects
    # better than FLUX when prompted correctly.
    # person_generation="ALLOW_ADULT" is the correct value for free API keys
    # (ALLOW_ALL is blocked and throws an enum error on free tier).

    def _generate_gemini(self, prompt: str, output_path: str, width: int, height: int) -> str:
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not set")
 
        from PIL import Image as PILImage
 
        logger.info(f"[Gemini Imagen 3] Generating: {prompt[:70]}…")
 
        # Map pixel dimensions to Gemini's supported aspect ratios
        if height > width:
            aspect_ratio = "9:16"     # TikTok portrait
        elif width > height:
            aspect_ratio = "16:9"     # landscape
        else:
            aspect_ratio = "1:1"
 
        # Use the module-level gemini_client (same pattern as script.py)
        response = gemini_client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                output_mime_type="image/jpeg",
                safety_filter_level="BLOCK_ONLY_HIGH",
                person_generation="ALLOW_ADULT",
            ),
        )
 
        if not response.generated_images:
            raise ValueError("Gemini Imagen returned no images — possible safety filter block")
 
        # image.image_bytes is raw JPEG bytes when output_mime_type='image/jpeg'
        image_bytes = response.generated_images[0].image.image_bytes
        img = PILImage.open(io.BytesIO(image_bytes))
 
        # Resize to exact pixel dimensions if Gemini returned a different size
        if img.size != (width, height):
            img = img.resize((width, height), PILImage.LANCZOS)
 
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=95)
 
        logger.info(f"[Gemini Imagen 3] ✓ Saved: {output_path}")
        return output_path

    # ── Provider 2: HuggingFace FLUX.1-schnell ───────────────────────────────
    # Free monthly quota — resets every month.
    # Uses your existing HF_API_KEY.
    # Good quality, especially for photorealistic scenes.

    async def _generate_huggingface(self, prompt: str, output_path: str, width: int, height: int) -> str:
        if not self.hf_key:
            raise ValueError("HF_API_KEY not set")

        from huggingface_hub import AsyncInferenceClient

        logger.info(f"[HuggingFace FLUX.1-schnell] Generating: {prompt[:70]}…")

        hf_client = AsyncInferenceClient(
            provider="hf-inference",
            api_key=self.hf_key,
        )

        pil_image = await hf_client.text_to_image(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=4,      # schnell is optimised for 1-4 steps
            model="black-forest-labs/FLUX.1-schnell",
        )

        buf = io.BytesIO()
        pil_image.save(buf, format="JPEG", quality=95)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(buf.getvalue())

        logger.info(f"[HuggingFace FLUX.1-schnell] ✓ Saved: {output_path}")
        return output_path

    # ── Provider 3: fal.ai FLUX.1-dev (paid last resort) ─────────────────────
    # Only reached if both free providers are exhausted or failing.
    # ~$0.05 per TikTok portrait image. Uses your existing FAL_KEY.

    def _generate_fal(self, prompt: str, output_path: str, width: int, height: int) -> str:
        if not self.fal_key:
            raise ValueError("FAL_KEY not set")

        import fal_client

        logger.info(f"[fal.ai FLUX.1-dev] Generating: {prompt[:70]}…")

        os.environ["FAL_KEY"] = self.fal_key
        result = fal_client.subscribe(
            "fal-ai/flux/dev",
            arguments={
                "prompt": prompt,
                "image_size": {"width": width, "height": height},
                "num_inference_steps": 28,
                "guidance_scale": 3.5,
                "num_images": 1,
                "enable_safety_checker": False,
            },
        )

        image_url = result["images"][0]["url"]
        img_data = requests.get(image_url, timeout=30)
        img_data.raise_for_status()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_data.content)

        logger.info(f"[fal.ai] ✓ Saved: {output_path}")
        return output_path

    # ── Core public method ────────────────────────────────────────────────────

    async def generate_image(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
        scene_context: str = "",
        health_mode: bool = False,
    ) -> str:
        """
        Generate a single image using the provider waterfall.
        Tries Gemini → HuggingFace → fal.ai until one succeeds.

        Args:
            prompt:       Visual description (use scene['image_prompt'] from script.py)
            output_path:  Where to save the JPEG
            width:        Pixels wide  (default 1080 — TikTok portrait)
            height:       Pixels tall  (default 1920 — TikTok portrait)
            scene_context: Extra context appended to prompt
            health_mode:  Append health-awareness suffixes (for MaternAlert videos)

        Returns:
            output_path on success
        Raises:
            RuntimeError if all providers fail
        """
        enhanced = enhance_prompt(prompt, scene_context=scene_context, health_mode=health_mode)

        # Note: _generate_huggingface is async, others are sync.
        # We handle this by wrapping sync providers normally and awaiting the async one.
        errors = []

        # 1. Gemini (sync)
        try:
            return self._generate_gemini(enhanced, output_path, width, height)
        except Exception as e:
            logger.warning(f"[images] Gemini Imagen 3 failed: {e}")
            errors.append(f"Gemini: {e}")

        # 2. HuggingFace (async)
        try:
            return await self._generate_huggingface(enhanced, output_path, width, height)
        except Exception as e:
            logger.warning(f"[images] HuggingFace FLUX.1-schnell failed: {e}")
            errors.append(f"HuggingFace: {e}")

        # 3. fal.ai (sync, paid last resort)
        try:
            return self._generate_fal(enhanced, output_path, width, height)
        except Exception as e:
            logger.warning(f"[images] fal.ai failed: {e}")
            errors.append(f"fal.ai: {e}")

        raise RuntimeError("All image providers failed:\n" + "\n".join(errors))

    # ── Batch method (identical signature to original) ────────────────────────

    async def generate_images(
        self,
        scenes: list,
        job_id: str,
        health_mode: bool = False,
    ) -> list:
        """
        Generates one image per scene, saves to OUTPUT_DIR.
        Returns list of (Path, duration_seconds) tuples for the renderer.

        Uses scene['image_prompt'] if present (from updated script.py),
        falls back to scene['description'] for backwards compatibility.
        """
        image_paths = []

        for i, scene in enumerate(scenes):
            # Prefer the structured image_prompt from the updated script.py
            raw_prompt = scene.get("image_prompt") or scene.get("description", "")

            # Prepend TikTok framing hint if not already in the prompt
            if "9:16" not in raw_prompt and "vertical" not in raw_prompt.lower():
                full_prompt = (
                    f"cinematic vertical 9:16 TikTok video frame, "
                    f"ultra realistic, sharp focus, professional photography, "
                    f"dramatic lighting, {raw_prompt}"
                )
            else:
                full_prompt = raw_prompt

            logger.info(f"Generating image {i + 1}/{len(scenes)}: {raw_prompt[:60]}…")

            img_path = OUTPUT_DIR / f"{job_id}_scene_{i}.jpg"

            try:
                await self.generate_image(
                    prompt=full_prompt,
                    output_path=str(img_path),
                    width=1080,
                    height=1920,
                    scene_context=scene.get("context", ""),
                    health_mode=health_mode,
                )
                image_paths.append((img_path, scene.get("duration", 5)))
                logger.info(f"✓ Scene {i + 1} saved → {img_path.name}")

            except RuntimeError as e:
                logger.error(f"Scene {i + 1} — all providers failed: {e}")
                image_paths.append((None, scene.get("duration", 5)))

        return image_paths


# ── Public factory (unchanged) ────────────────────────────────────────────────

def get_image_client() -> ImageGenerationClient:
    """Returns the active image generation client."""
    return ImageGenerationClient()


# Backwards-compatible alias
get_pollinations_client = get_image_client