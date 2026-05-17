import io
from pathlib import Path
from typing import Optional
from config import OUTPUT_DIR, HF_API_KEY

# ─────────────────────────────────────────────────────────────────────────────
# POLLINATIONS CLIENT (commented out — replaced by HuggingFace SDK)
# ─────────────────────────────────────────────────────────────────────────────
# import httpx
# from urllib.parse import quote
# from config import OUTPUT_DIR, POLLINATIONS_API_KEY
#
# class PollinationsClient:
#     BASE_URL = "https://gen.pollinations.ai/image"
#
#     def __init__(self, api_key: Optional[str] = None):
#         self.api_key = api_key
#
#     async def generate_image(self, prompt, width=576, height=1024, seed=None,
#                              nologo=True, model="zimage") -> bytes:
#         params = {"width": width, "height": height, "nologo": str(nologo).lower(), "model": model}
#         if seed is not None: params["seed"] = seed
#         if self.api_key:     params["key"] = self.api_key
#         url = f"{self.BASE_URL}/{quote(prompt)}"
#         async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
#             res = await client.get(url, params=params)
#             if res.status_code == 402:
#                 raise ValueError("Pollinations requires pollen credits — switch to HuggingFace.")
#             if res.status_code != 200:
#                 raise ValueError(f"Pollinations error ({res.status_code}): {res.text[:200]}")
#             return res.content
#
#     async def generate_images(self, scenes, job_id) -> list:
#         image_paths = []
#         for i, scene in enumerate(scenes):
#             full_prompt = (f"cinematic vertical 9:16 TikTok video frame, ultra realistic, "
#                            f"dramatic lighting, {scene['description']}")
#             image_bytes = await self.generate_image(full_prompt, seed=42+i)
#             img_path = OUTPUT_DIR / f"{job_id}_scene_{i}.jpg"
#             img_path.write_bytes(image_bytes)
#             image_paths.append((img_path, scene.get("duration", 5)))
#         return image_paths
#
# def get_pollinations_client():
#     return PollinationsClient(api_key=POLLINATIONS_API_KEY)
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# HUGGING FACE IMAGE CLIENT  —  uses the official huggingface_hub SDK
#
# Why SDK over raw httpx?
#   • Handles provider routing automatically (hf-inference, fal-ai, etc.)
#   • Built-in cold-start polling — no manual retry loops needed
#   • Request/response format is provider-agnostic
#   • AsyncInferenceClient is fully async-compatible with FastAPI
#
# Models:
#   Primary  → black-forest-labs/FLUX.1-schnell  (4-step, very fast, free)
#   Fallback → black-forest-labs/FLUX.1-dev      (20-step, higher fidelity)
#
# Setup:
#   1. Free account at https://huggingface.co
#   2. Settings → Access Tokens → New token (Read permission)
#   3. Add HF_API_KEY=hf_... to your .env
# ─────────────────────────────────────────────────────────────────────────────

from huggingface_hub import AsyncInferenceClient  # pip install huggingface_hub

HF_MODEL_PRIMARY  = "black-forest-labs/FLUX.1-schnell"
HF_MODEL_FALLBACK = "black-forest-labs/FLUX.1-dev"


class HuggingFaceClient:
    """
    Image generation client backed by the Hugging Face Inference SDK.
    Calls FLUX.1-schnell first; falls back to FLUX.1-dev on any error.
    The SDK handles cold-start retries, provider routing, and response parsing.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError(
                "HF_API_KEY is missing. Get a free token at "
                "https://huggingface.co/settings/tokens and add it to your .env."
            )
        # AsyncInferenceClient is the async-native SDK client
        self._client = AsyncInferenceClient(
            provider="hf-inference",  # HF's own inference cluster — always free tier
            api_key=api_key,
        )

    async def generate_image(
        self,
        prompt: str,
        width: int = 576,
        height: int = 1024,
        seed: Optional[int] = None,
    ) -> bytes:
        """
        Generates one image and returns raw JPEG bytes.
        Tries FLUX.1-schnell first, falls back to FLUX.1-dev on failure.
        """
        kwargs = dict(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=4,   # schnell is optimised for 4 steps
        )
        if seed is not None:
            kwargs["seed"] = seed

        # Primary: FLUX.1-schnell
        try:
            pil_image = await self._client.text_to_image(
                **kwargs,
                model=HF_MODEL_PRIMARY,
            )
            return _pil_to_jpeg_bytes(pil_image)

        except Exception as primary_error:
            print(
                f"[HuggingFace] Primary model ({HF_MODEL_PRIMARY}) failed: {primary_error}\n"
                f"              Falling back to {HF_MODEL_FALLBACK}…"
            )

        # Fallback: FLUX.1-dev (needs more steps for quality)
        kwargs["num_inference_steps"] = 20
        pil_image = await self._client.text_to_image(
            **kwargs,
            model=HF_MODEL_FALLBACK,
        )
        return _pil_to_jpeg_bytes(pil_image)

    async def generate_images(self, scenes: list, job_id: str) -> list:
        """
        Generates one image per scene, saves to OUTPUT_DIR.
        Returns a list of (Path, duration_seconds) tuples for the renderer.
        """
        image_paths = []
        for i, scene in enumerate(scenes):
            full_prompt = (
                f"cinematic vertical 9:16 TikTok video frame, "
                f"ultra realistic, sharp focus, professional photography, "
                f"dramatic lighting, {scene['description']}"
            )
            print(f"[HuggingFace] Generating image {i + 1}/{len(scenes)}: "
                  f"{scene['description'][:60]}…")

            image_bytes = await self.generate_image(
                prompt=full_prompt,
                seed=42 + i,
                width=576,
                height=1024,
            )

            img_path = OUTPUT_DIR / f"{job_id}_scene_{i}.jpg"
            img_path.write_bytes(image_bytes)
            image_paths.append((img_path, scene.get("duration", 5)))
            print(f"[HuggingFace] ✓ Scene {i + 1} saved → {img_path.name}")

        return image_paths


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pil_to_jpeg_bytes(pil_image) -> bytes:
    """Converts a PIL Image returned by the SDK to raw JPEG bytes."""
    buf = io.BytesIO()
    pil_image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ── Public factory ────────────────────────────────────────────────────────────

def get_image_client() -> HuggingFaceClient:
    """Returns the active image generation client (HuggingFace SDK)."""
    return HuggingFaceClient(api_key=HF_API_KEY)


# Backwards-compatible alias in case any other module still imports the old name
get_pollinations_client = get_image_client