"""Shared helpers for studio AI specialists."""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel

from services.ai.client import generate_json
from services.ai.exceptions import ValidationError
from services.ai.json_repair import attempt_json_repair, is_likely_truncated
from services.ai.prompts import load_prompt

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def generate_structured_artifact(
    *,
    prompt_name: str,
    model: type[T],
    variables: dict[str, Any],
    temperature: float = 0.45,
    max_tokens: int = 3000,
    attempts: int = 2,
) -> T:
    """
    Run one isolated prompt and validate the result into a Pydantic model.
    
    Implements smart retry with JSON repair:
    - Attempt 1: Normal generation
    - If truncated: Try JSON repair before regenerating
    - Attempt 2: Regenerate with adjusted parameters
    """
    base_prompt = load_prompt(prompt_name, **variables)
    system = load_prompt("base")
    last_raw: Any = None
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        retry_note = ""
        if attempt > 1:
            retry_note = (
                "\n\nPrevious attempt failed validation. Return one complete, "
                "strict JSON object only. Keep values concise. Do not truncate."
            )
        try:
            raw = await generate_json(
                prompt=base_prompt + retry_note,
                system=system,
                temperature=max(0.1, temperature - (0.15 * (attempt - 1))),
                max_tokens=min(3800, max_tokens + (500 * (attempt - 1))),
                response_schema=_sanitize_schema_for_gemini(model.model_json_schema()),
            )
            last_raw = raw
            return model.model_validate(raw)
            
        except ValidationError as exc:
            last_exc = exc
            last_raw = exc.raw if hasattr(exc, 'raw') else None
            
            logger.warning(
                "%s structured attempt %d/%d failed | error=%s",
                model.__name__,
                attempt,
                attempts,
                str(exc)[:200],
            )
            
            # Only try repair on first failure (before expensive regeneration)
            if attempt == 1 and last_raw and isinstance(last_raw, str):
                if is_likely_truncated(last_raw):
                    logger.info("Attempting JSON repair on truncated response...")
                    repaired = attempt_json_repair(last_raw)
                    if repaired:
                        try:
                            result = model.model_validate(repaired)
                            logger.info(
                                "✓ JSON repair succeeded for %s — avoided expensive regeneration",
                                model.__name__,
                            )
                            return result
                        except Exception as repair_exc:
                            logger.warning(
                                "JSON repair produced valid JSON but failed model validation: %s",
                                repair_exc,
                            )
                    else:
                        logger.warning("JSON repair failed — will regenerate")
                else:
                    logger.info("Response not truncated — regenerating with adjusted parameters")
            
            # Continue to next attempt
            continue
            
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "%s structured attempt %d/%d failed: %s",
                model.__name__,
                attempt,
                attempts,
                exc,
            )

    raise ValidationError(
        f"{model.__name__} validation failed after {attempts} attempts: {last_exc}",
        raw=json.dumps(last_raw, default=str)[:600] if last_raw is not None else "",
    )

def _sanitize_schema_for_gemini(schema: dict) -> dict:
    """Gemini's response_schema is a restricted OpenAPI subset and rejects
    some standard JSON Schema keywords Pydantic emits — most commonly
    additionalProperties on any dict-typed field. Strip these recursively
    so the same schema works for Gemini without weakening it for Groq."""
    if isinstance(schema, dict):
        return {
            k: _sanitize_schema_for_gemini(v)
            for k, v in schema.items()
            if k != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_sanitize_schema_for_gemini(item) for item in schema]
    return schema