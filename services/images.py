# import io
# import os
# import logging
# import requests
# from pathlib import Path
# from typing import Optional
# from config import OUTPUT_DIR, GEMINI_API_KEY, HF_API_KEY, FAL_KEY
# from google import genai as google_genai
# from google.genai import types as genai_types

# logger = logging.getLogger(__name__)
# gemini_client = google_genai.Client(api_key=GEMINI_API_KEY)

# # ─────────────────────────────────────────────────────────────────────────────
# # PROVIDER WATERFALL (first success wins):
# #
# #   1. Google Gemini 3 Pro Image  — FREE 500 images/day, no credit card
# #                                uses your existing GEMINI_API_KEY
# #
# #   2. HuggingFace FLUX.1-schnell — FREE monthly quota (resets each month)
# #                                   uses your existing HF_API_KEY
# #
# #   3. fal.ai FLUX.1-dev       — PAID last resort (~$0.05/image)
# #                                uses your existing FAL_KEY
# #
# # No new accounts or API keys needed — everything uses what you already have.
# # ─────────────────────────────────────────────────────────────────────────────


# def enhance_prompt(base_prompt: str, scene_context: str = "", health_mode: bool = False) -> str:
#     """Append cinematic suffixes unless the prompt already contains them."""
#     if "photorealistic" in base_prompt.lower():
#         return base_prompt

#     parts = [base_prompt]
#     if scene_context:
#         parts.append(scene_context)

#     parts.extend([
#         "photorealistic",
#         "sharp focus",
#         "cinematic lighting",
#         "4K",
#         "high detail",
#     ])

#     if health_mode:
#         parts.extend(["professional", "clean", "trustworthy", "warm hopeful atmosphere"])

#     return ", ".join(parts)


# class ImageGenerationClient:
#     """
#     Image generation with 3-provider waterfall:
#     Gemini Imagen 3 (free 500/day) → HuggingFace FLUX.1-schnell (free monthly) → fal.ai (paid)
#     """

#     def __init__(
#         self,
#         gemini_key: Optional[str] = None,
#         hf_key: Optional[str] = None,
#         fal_key: Optional[str] = None,
#     ):
#         self.gemini_key = gemini_key or GEMINI_API_KEY
#         self.hf_key = hf_key or HF_API_KEY
#         self.fal_key = fal_key or FAL_KEY

#         if not any([self.gemini_key, self.hf_key, self.fal_key]):
#             raise ValueError(
#                 "At least one of GEMINI_API_KEY, HF_API_KEY, or FAL_KEY must be set."
#             )

#     # ── Provider 1: Google Gemini Imagen 3 ───────────────────────────────────
#     # 500 images/day free. Uses your existing GEMINI_API_KEY.
#     # Best quality of the free options — handles Nigerian/African subjects
#     # better than FLUX when prompted correctly.
#     # person_generation="ALLOW_ADULT" is the correct value for free API keys
#     # (ALLOW_ALL is blocked and throws an enum error on free tier).

#     def _generate_gemini(self, prompt: str, output_path: str, width: int, height: int) -> str:
#         if not self.gemini_key:
#             raise ValueError("GEMINI_API_KEY not set")
 
#         from PIL import Image as PILImage
 
#         logger.info(f"[Gemini Imagen 3] Generating: {prompt[:70]}…")
 
#         # Map pixel dimensions to Gemini's supported aspect ratios
#         if height > width:
#             aspect_ratio = "9:16"     # TikTok portrait
#         elif width > height:
#             aspect_ratio = "16:9"     # landscape
#         else:
#             aspect_ratio = "1:1"
 
#         # Use the module-level gemini_client (same pattern as script.py)
#         response = gemini_client.models.generate_images(
#             model="gemini-3.0-pro-image-001",
#             prompt=prompt,
#             config=genai_types.GenerateImagesConfig(
#                 number_of_images=1,
#                 aspect_ratio=aspect_ratio,
#                 output_mime_type="image/jpeg",
#                 safety_filter_level="BLOCK_ONLY_HIGH",
#                 person_generation="ALLOW_ADULT",
#             ),
#         )
 
#         if not response.generated_images:
#             raise ValueError("Gemini Imagen returned no images — possible safety filter block")
 
#         # image.image_bytes is raw JPEG bytes when output_mime_type='image/jpeg'
#         image_bytes = response.generated_images[0].image.image_bytes
#         img = PILImage.open(io.BytesIO(image_bytes))
 
#         # Resize to exact pixel dimensions if Gemini returned a different size
#         if img.size != (width, height):
#             img = img.resize((width, height), PILImage.LANCZOS)
 
#         Path(output_path).parent.mkdir(parents=True, exist_ok=True)
#         img.save(output_path, "JPEG", quality=95)
 
#         logger.info(f"[Gemini Imagen 3] ✓ Saved: {output_path}")
#         return output_path

#     # ── Provider 2: HuggingFace FLUX.1-schnell ───────────────────────────────
#     # Free monthly quota — resets every month.
#     # Uses your existing HF_API_KEY.
#     # Good quality, especially for photorealistic scenes.

#     async def _generate_huggingface(self, prompt: str, output_path: str, width: int, height: int) -> str:
#         if not self.hf_key:
#             raise ValueError("HF_API_KEY not set")

#         from huggingface_hub import AsyncInferenceClient

#         logger.info(f"[HuggingFace FLUX.1-schnell] Generating: {prompt[:70]}…")

#         hf_client = AsyncInferenceClient(
#             provider="hf-inference",
#             api_key=self.hf_key,
#         )

#         pil_image = await hf_client.text_to_image(
#             prompt=prompt,
#             width=width,
#             height=height,
#             num_inference_steps=4,      # schnell is optimised for 1-4 steps
#             model="black-forest-labs/FLUX.1-schnell",
#         )

#         buf = io.BytesIO()
#         pil_image.save(buf, format="JPEG", quality=95)

#         Path(output_path).parent.mkdir(parents=True, exist_ok=True)
#         with open(output_path, "wb") as f:
#             f.write(buf.getvalue())

#         logger.info(f"[HuggingFace FLUX.1-schnell] ✓ Saved: {output_path}")
#         return output_path

#     # ── Provider 3: fal.ai FLUX.1-dev (paid last resort) ─────────────────────
#     # Only reached if both free providers are exhausted or failing.
#     # ~$0.05 per TikTok portrait image. Uses your existing FAL_KEY.

#     def _generate_fal(self, prompt: str, output_path: str, width: int, height: int) -> str:
#         if not self.fal_key:
#             raise ValueError("FAL_KEY not set")

#         import fal_client

#         logger.info(f"[fal.ai FLUX.1-dev] Generating: {prompt[:70]}…")

#         os.environ["FAL_KEY"] = self.fal_key
#         result = fal_client.subscribe(
#             "fal-ai/flux/dev",
#             arguments={
#                 "prompt": prompt,
#                 "image_size": {"width": width, "height": height},
#                 "num_inference_steps": 28,
#                 "guidance_scale": 3.5,
#                 "num_images": 1,
#                 "enable_safety_checker": False,
#             },
#         )

#         image_url = result["images"][0]["url"]
#         img_data = requests.get(image_url, timeout=30)
#         img_data.raise_for_status()

#         Path(output_path).parent.mkdir(parents=True, exist_ok=True)
#         with open(output_path, "wb") as f:
#             f.write(img_data.content)

#         logger.info(f"[fal.ai] ✓ Saved: {output_path}")
#         return output_path

#     # ── Core public method ────────────────────────────────────────────────────

#     async def generate_image(
#         self,
#         prompt: str,
#         output_path: str,
#         width: int = 1080,
#         height: int = 1920,
#         scene_context: str = "",
#         health_mode: bool = False,
#     ) -> str:
#         """
#         Generate a single image using the provider waterfall.
#         Tries Gemini → HuggingFace → fal.ai until one succeeds.

#         Args:
#             prompt:       Visual description (use scene['image_prompt'] from script.py)
#             output_path:  Where to save the JPEG
#             width:        Pixels wide  (default 1080 — TikTok portrait)
#             height:       Pixels tall  (default 1920 — TikTok portrait)
#             scene_context: Extra context appended to prompt
#             health_mode:  Append health-awareness suffixes (for MaternAlert videos)

#         Returns:
#             output_path on success
#         Raises:
#             RuntimeError if all providers fail
#         """
#         enhanced = enhance_prompt(prompt, scene_context=scene_context, health_mode=health_mode)

#         # Note: _generate_huggingface is async, others are sync.
#         # We handle this by wrapping sync providers normally and awaiting the async one.
#         errors = []

#         # 1. Gemini (sync)
#         try:
#             return self._generate_gemini(enhanced, output_path, width, height)
#         except Exception as e:
#             logger.warning(f"[images] Gemini Imagen 3 failed: {e}")
#             errors.append(f"Gemini: {e}")

#         # 2. HuggingFace (async)
#         try:
#             return await self._generate_huggingface(enhanced, output_path, width, height)
#         except Exception as e:
#             logger.warning(f"[images] HuggingFace FLUX.1-schnell failed: {e}")
#             errors.append(f"HuggingFace: {e}")

#         # 3. fal.ai (sync, paid last resort)
#         try:
#             return self._generate_fal(enhanced, output_path, width, height)
#         except Exception as e:
#             logger.warning(f"[images] fal.ai failed: {e}")
#             errors.append(f"fal.ai: {e}")

#         raise RuntimeError("All image providers failed:\n" + "\n".join(errors))

#     # ── Batch method (identical signature to original) ────────────────────────

#     async def generate_images(
#         self,
#         scenes: list,
#         job_id: str,
#         health_mode: bool = False,
#     ) -> list:
#         """
#         Generates one image per scene, saves to OUTPUT_DIR.
#         Returns list of (Path, duration_seconds) tuples for the renderer.

#         Uses scene['image_prompt'] if present (from updated script.py),
#         falls back to scene['description'] for backwards compatibility.
#         """
#         image_paths = []

#         for i, scene in enumerate(scenes):
#             # Prefer the structured image_prompt from the updated script.py
#             raw_prompt = scene.get("image_prompt") or scene.get("description", "")

#             # Prepend TikTok framing hint if not already in the prompt
#             if "9:16" not in raw_prompt and "vertical" not in raw_prompt.lower():
#                 full_prompt = (
#                     f"cinematic vertical 9:16 TikTok video frame, "
#                     f"ultra realistic, sharp focus, professional photography, "
#                     f"dramatic lighting, {raw_prompt}"
#                 )
#             else:
#                 full_prompt = raw_prompt

#             logger.info(f"Generating image {i + 1}/{len(scenes)}: {raw_prompt[:60]}…")

#             img_path = OUTPUT_DIR / f"{job_id}_scene_{i}.jpg"

#             try:
#                 await self.generate_image(
#                     prompt=full_prompt,
#                     output_path=str(img_path),
#                     width=1080,
#                     height=1920,
#                     scene_context=scene.get("context", ""),
#                     health_mode=health_mode,
#                 )
#                 image_paths.append((img_path, scene.get("duration", 5)))
#                 logger.info(f"✓ Scene {i + 1} saved → {img_path.name}")

#             except RuntimeError as e:
#                 logger.error(f"Scene {i + 1} — all providers failed: {e}")
#                 image_paths.append((None, scene.get("duration", 5)))

#         return image_paths


# # ── Public factory (unchanged) ────────────────────────────────────────────────

# def get_image_client() -> ImageGenerationClient:
#     """Returns the active image generation client."""
#     return ImageGenerationClient()


# # Backwards-compatible alias
# get_pollinations_client = get_image_client


import io
import os
import time
import logging
import requests
from pathlib import Path
from typing import Optional
from config import OUTPUT_DIR, FAL_KEY, PIXAZO_API_KEY

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER WATERFALL (first success wins):
#
#   1. Pixazo FLUX.1-schnell FREE  — genuinely free, ~10 req/min, ~1.2s/image
#                                    uses Ocp-Apim-Subscription-Key header
#                                    gateway: gateway.pixazo.ai/flux-schnell-free
#
#   2. Pixazo Flux 2 Klein         — paid fallback, ~$0.0014 per 1448px image
#                                    direct sync response (no polling needed)
#                                    gateway: gateway.pixazo.ai/flux-2-klein-4b
#
#   3. fal.ai FLUX.1-dev           — existing paid last resort (~$0.05/image)
#
# Auth for Pixazo: Ocp-Apim-Subscription-Key header (NOT Authorization: Bearer)
# Add PIXAZO_API_KEY to your .env
# ─────────────────────────────────────────────────────────────────────────────

PIXAZO_API_KEY = os.getenv("PIXAZO_API_KEY", "")

# Pixazo has two different polling patterns:
#   - Schnell Free: POST to /checkStatus with {"requestId": "..."}, camelCase
#   - Klein/other:  GET  to /v2/requests/status/{request_id}, UPPERCASE status
PIXAZO_SCHNELL_BASE_URL = "https://gateway.pixazo.ai/flux-1-schnell"
PIXAZO_KLEIN_STATUS_URL = "https://gateway.pixazo.ai/v2/requests/status/{request_id}"

PIXAZO_HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
}

# Polling settings
POLL_INTERVAL = 5       # seconds between status checks
POLL_TIMEOUT  = 120     # max seconds to wait for completion


def _pixazo_headers() -> dict:
    return {**PIXAZO_HEADERS, "Ocp-Apim-Subscription-Key": PIXAZO_API_KEY}


def _poll_pixazo_schnell(request_id: str, base_url: str) -> str:
    """
    Poll Pixazo Schnell Free via POST to /checkStatus.
    Their docs: POST {"requestId": "..."} → check data["status"] (lowercase).
    Returns image URL when complete.
    """
    check_url = f"{base_url}/checkStatus"
    deadline = time.time() + POLL_TIMEOUT

    while time.time() < deadline:
        resp = requests.post(
            check_url,
            headers=_pixazo_headers(),
            json={"requestId": request_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "").lower()

        if status == "completed":
            # Response shape varies — try common fields
            image_url = (
                data.get("imageUrl")
                or data.get("image_url")
                or data.get("output")
                or (data.get("result") or {}).get("imageUrl")
            )
            if not image_url:
                raise ValueError(f"Pixazo schnell COMPLETED but no image URL in response: {data}")
            return image_url

        if status in ("failed", "error"):
            raise ValueError(f"Pixazo schnell job {request_id} failed: {data.get('error') or data}")

        logger.debug(f"[Pixazo Schnell] Status: {status} — waiting {POLL_INTERVAL}s…")
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Pixazo schnell job {request_id} timed out after {POLL_TIMEOUT}s")


def _poll_pixazo_klein(request_id: str) -> str:
    """
    Poll Pixazo Klein/other models via GET to /v2/requests/status.
    Status values are UPPERCASE: QUEUED, PROCESSING, COMPLETED, FAILED, ERROR.
    """
    url = PIXAZO_KLEIN_STATUS_URL.format(request_id=request_id)
    deadline = time.time() + POLL_TIMEOUT

    while time.time() < deadline:
        resp = requests.get(url, headers=_pixazo_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "")

        if status == "COMPLETED":
            media_urls = data.get("output", {}).get("media_url", [])
            if not media_urls:
                raise ValueError(f"Pixazo COMPLETED but no media_url in response: {data}")
            return media_urls[0]

        if status in ("FAILED", "ERROR"):
            raise ValueError(f"Pixazo job {request_id} failed: {data.get('error')}")

        logger.debug(f"[Pixazo Klein] Status: {status} — waiting {POLL_INTERVAL}s…")
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Pixazo job {request_id} timed out after {POLL_TIMEOUT}s")


def _download_and_save(image_url: str, output_path: str, width: int, height: int) -> str:
    """Download image from URL, resize to exact dimensions, save as JPEG."""
    from PIL import Image as PILImage

    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()

    img = PILImage.open(io.BytesIO(resp.content))
    if img.size != (width, height):
        img = img.resize((width, height), PILImage.LANCZOS)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def enhance_prompt(base_prompt: str, scene_context: str = "", health_mode: bool = False) -> str:
    """Append cinematic suffixes unless the prompt already contains them."""
    if "photorealistic" in base_prompt.lower():
        return base_prompt

    parts = [base_prompt]
    if scene_context:
        parts.append(scene_context)

    parts.extend(["photorealistic", "sharp focus", "cinematic lighting", "4K", "high detail"])

    if health_mode:
        parts.extend(["professional", "clean", "trustworthy", "warm hopeful atmosphere"])

    return ", ".join(parts)


class ImageGenerationClient:
    """
    Image generation with 3-provider waterfall:
      1. Pixazo FLUX.1-schnell Free (free, async with polling)
      2. Pixazo Flux 2 Klein        (paid ~$0.0014, sync direct response)
      3. fal.ai FLUX.1-dev          (paid ~$0.05, existing last resort)
    """

    def __init__(self, pixazo_key: Optional[str] = None, fal_key: Optional[str] = None):
        global PIXAZO_API_KEY
        if pixazo_key:
            PIXAZO_API_KEY = pixazo_key
        elif not PIXAZO_API_KEY:
            PIXAZO_API_KEY = os.getenv("PIXAZO_API_KEY", "")

        self.fal_key = fal_key or FAL_KEY

    # ── Provider 1: Pixazo FLUX.1-schnell Free ────────────────────────────────
    # Async: POST → get request_id → poll until COMPLETED → download image.
    # Free tier, ~10 req/min, ~1.2s generation time.
    # Docs: https://www.pixazo.ai/models/flux (section 7: Flux 1 Schnell - FREE)

    def _generate_pixazo_schnell(self, prompt: str, output_path: str, width: int, height: int) -> str:
        if not PIXAZO_API_KEY:
            raise ValueError("PIXAZO_API_KEY not set")

        logger.info(f"[Pixazo Schnell Free] Generating: {prompt[:60]}…")

        # Snap to nearest supported pixel size per their docs
        supported_sizes = [512, 768, 1024, 1280, 1536, 1920]
        snap_w = min(supported_sizes, key=lambda s: abs(s - width))
        snap_h = min(supported_sizes, key=lambda s: abs(s - height))

        resp = requests.post(
            f"{PIXAZO_SCHNELL_BASE_URL}/v1/getData",
            headers=_pixazo_headers(),
            json={
                "prompt": prompt,
                "num_steps": 4,
                "width": snap_w,
                "height": snap_h,
                "seed": 15,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # The endpoint returns the output URL directly, no polling needed
        image_url = data.get("output")
        if not image_url:
            raise ValueError(f"Pixazo schnell returned no output URL: {data}")

        result = _download_and_save(image_url, output_path, width, height)
        logger.info(f"[Pixazo Schnell Free] ✓ Saved: {output_path}")
        return result

    # ── Provider 2: Pixazo Flux 2 Klein (paid, sync, very cheap) ─────────────
    # Synchronous — returns image URL directly, no polling.
    # Supports exact pixel dimensions (512, 1024, 1448, 2048).
    # At 1448px: $0.0014/image → 12-scene video costs ~$0.017 total.
    # Docs: https://www.pixazo.ai/models/flux (section 4: Flux 2 Klein)

    def _generate_pixazo_klein(self, prompt: str, output_path: str, width: int, height: int) -> str:
        if not PIXAZO_API_KEY:
            raise ValueError("PIXAZO_API_KEY not set")

        logger.info(f"[Pixazo Flux 2 Klein] Generating: {prompt[:60]}…")

        # Klein supports: 512, 1024, 1448, 2048 — pick closest supported size
        supported = [512, 1024, 1448, 2048]
        px = min(supported, key=lambda s: abs(s - max(width, height)))

        resp = requests.post(
            "https://gateway.pixazo.ai/flux-2-klein-4b/v1/generateImage",
            headers=_pixazo_headers(),
            json={
                "prompt": prompt,
                "steps": 25,
                "width": px,
                "height": px,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        image_url = data.get("output")
        if not image_url:
            raise ValueError(f"Pixazo Klein returned no output URL: {data}")

        result = _download_and_save(image_url, output_path, width, height)
        logger.info(f"[Pixazo Flux 2 Klein] ✓ Saved: {output_path}")
        return result

    # ── Provider 3: fal.ai FLUX.1-dev (existing last resort) ─────────────────

    def _generate_fal(self, prompt: str, output_path: str, width: int, height: int) -> str:
        if not self.fal_key:
            raise ValueError("FAL_KEY not set")

        import fal_client

        logger.info(f"[fal.ai FLUX.1-dev] Generating: {prompt[:60]}…")

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
        return _download_and_save(image_url, output_path, width, height)

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
        Generate a single image using the provider waterfall:
        Pixazo Schnell Free → Pixazo Klein → fal.ai
        """
        enhanced = enhance_prompt(prompt, scene_context=scene_context, health_mode=health_mode)
        errors = []

        for name, fn in [
            ("Pixazo Schnell Free", lambda: self._generate_pixazo_schnell(enhanced, output_path, width, height)),
            ("Pixazo Flux 2 Klein", lambda: self._generate_pixazo_klein(enhanced, output_path, width, height)),
            ("fal.ai",             lambda: self._generate_fal(enhanced, output_path, width, height)),
        ]:
            try:
                return fn()
            except Exception as e:
                logger.warning(f"[images] {name} failed: {e}")
                errors.append(f"{name}: {e}")

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

        Uses scene['image_prompt'] if present (updated script.py),
        falls back to scene['description'] for backwards compatibility.
        """
        image_paths = []

        for i, scene in enumerate(scenes):
            raw_prompt = scene.get("image_prompt") or scene.get("description", "")

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


# ── Public factory ────────────────────────────────────────────────────────────

def get_image_client() -> ImageGenerationClient:
    return ImageGenerationClient()


# Backwards-compatible alias
get_pollinations_client = get_image_client