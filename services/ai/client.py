"""
services/ai/client.py — Unified AI client with automatic provider failover.

Public API
----------
    generate_text(prompt, system, temperature, max_tokens) -> str
    generate_json(prompt, system, schema, temperature, max_tokens) -> dict

Failover chain (configurable via PROVIDER_ORDER env var):
  1. Groq  (OpenAI-compatible SDK, fast)
  2. Gemini (google-genai SDK)
  3. ProviderError raised

Logging
-------
  Every call logs: provider used, latency (ms), token count where available.
  Fallback events are logged at WARNING level.
  Validation failures are logged at ERROR level.
"""

from __future__ import annotations

import json
import asyncio
import logging
import re
import time
from typing import Any, Optional, TYPE_CHECKING

from services.ai.exceptions import AIResponseError, ProviderError, ValidationError
from services.ai.providers import ProviderConfig, ProviderName, get_enabled_providers

try:  # Imported at module scope so tests can patch SDK calls directly.
    # pyrefly: ignore [missing-import]
    from google import genai
    # pyrefly: ignore [missing-import]
    from google.genai import types as genai_types
except Exception:  # pragma: no cover - handled at runtime when Gemini is used
    genai = None
    genai_types = None

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ── Retry constants ────────────────────────────────────────────────────────────

# HTTP status codes that indicate a transient failure (safe to retry)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Exception substrings that identify transient failures
_RETRYABLE_MESSAGES = {
    "timeout", "rate limit", "rate_limit", "overloaded", "service unavailable",
    "connection", "network", "503", "502", "429",
    "json_validate_failed", "max completion tokens reached",
    "empty content",
}

# Gemini rate limiting
_GEMINI_MIN_INTERVAL = 12.5  # 60s / 5 RPM, with a small safety margin
_gemini_lock = asyncio.Lock()
_gemini_last_call_at = 0.0

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _gemini_rate_gate() -> None:
    global _gemini_last_call_at
    async with _gemini_lock:
        now = time.monotonic()
        wait = _GEMINI_MIN_INTERVAL - (now - _gemini_last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _gemini_last_call_at = time.monotonic()

_MISTRAL_MIN_INTERVAL = 31.0  # 60s / 2 RPM, small safety margin
_mistral_lock = asyncio.Lock()
_mistral_last_call_at = 0.0

async def _mistral_rate_gate() -> None:
    global _mistral_last_call_at
    async with _mistral_lock:
        now = time.monotonic()
        wait = _MISTRAL_MIN_INTERVAL - (now - _mistral_last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _mistral_last_call_at = time.monotonic()


def _is_retryable(exc: Exception) -> bool:
    """Decide whether an exception from a provider deserves a failover attempt."""
    msg = str(exc).lower()
    return any(kw in msg for kw in _RETRYABLE_MESSAGES)


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json … ``` or ``` … ``` wrappers that some models include."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    msg = str(exc)
    match = re.search(r"(?:try again in|retry in)\s+([0-9]+(?:\.[0-9]+)?)\s*s", msg, re.IGNORECASE)
    if match:
        return min(8.0, max(0.5, float(match.group(1)) + 0.25))
    return min(8.0, 0.75 * attempt)


def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce provider token metadata to an int without letting None leak into math."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_percent(part: Any, total: Any) -> float:
    """Return part/total as a percentage, guarding all provider metadata values."""
    numerator = _safe_int(part)
    denominator = _safe_int(total)
    if denominator <= 0:
        return 0.0
    return numerator / denominator * 100


def _clamp_tokens_for_provider(cfg: ProviderConfig, prompt: str, system: str, requested_max_tokens: int) -> int:
    """
    Some providers enforce a hard cap on TOTAL context (prompt + completion),
    not just output — Mistral' free tier is 8,192 total. Agents size their
    max_tokens for whichever provider they were built against (usually Groq
    or Gemini's much larger budgets), so without this, a request that's
    perfectly fine for Groq gets forwarded unmodified to Mistral and
    rejected outright instead of gracefully truncating.
    """
    estimated_prompt_tokens = max(1, (len(prompt) + len(system)) // 4)  # same rough estimator already used in script_writer_v2.py
    total_budget = cfg.max_total_tokens - estimated_prompt_tokens
    return max(64, min(requested_max_tokens, cfg.max_output_tokens, total_budget))

# ── Provider callers ──────────────────────────────────────────────────────────

async def _call_groq(cfg, *, prompt, system, temperature, max_tokens, json_mode):
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=cfg.timeout)
    model_name = cfg.json_model if json_mode else cfg.model
    if cfg.name == ProviderName.MISTRAL:
        await _mistral_rate_gate()

    kwargs = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    # gpt-oss is a genuine reasoning model — unlike Llama 3.3, it can spend
    # the entire max_tokens budget on invisible chain-of-thought and return
    # empty content, especially under tight per-agent budgets sized for a
    # non-reasoning model. Minimize reasoning effort so tokens go to the
    # actual answer instead — same fix class as Gemini's thinking_budget=0.
    if "gpt-oss" in model_name:
        kwargs["reasoning_effort"] = "low"

    response = await client.chat.completions.create(**kwargs)

    finish_reason = response.choices[0].finish_reason or "unknown"
    usage = response.usage
    
    metadata = {
        "finish_reason": finish_reason,
        "prompt_tokens": _safe_int(getattr(usage, "prompt_tokens", 0) if usage else 0),
        "output_tokens": _safe_int(getattr(usage, "completion_tokens", 0) if usage else 0),
        "total_tokens": _safe_int(getattr(usage, "total_tokens", 0) if usage else 0),
    }

    content = response.choices[0].message.content
    if not content:
        raise AIResponseError("Groq returned empty content")
    
    return content, metadata


async def _call_gemini(
    cfg: ProviderConfig,
    *,
    prompt: str,
    system: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    response_schema: Optional[dict[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    """
    Calls Gemini via the google-genai SDK.
    
    Phase 2A Improvements:
    - Disables thinking for JSON mode (thinking_budget=0)
    - Uses response_mime_type="application/json" for structured output
    - Supports optional response_schema for strict JSON validation
    - Comprehensive token usage diagnostics
    
    Returns tuple of (content, metadata) where metadata contains:
    - finish_reason: why generation stopped
    - prompt_tokens: input token count
    - output_tokens: output token count (candidates_token_count)
    - thoughts_tokens: internal reasoning token count (gemini-specific)
    - total_tokens: combined count (what actually matters for limits)
    - json_mode: whether JSON mode was enabled
    - thinking_disabled: whether thinking was explicitly disabled
    """
    if genai is None or genai_types is None:
        raise ProviderError(
            "google-genai SDK is not installed but Gemini provider was selected.",
            provider=cfg.name.value,
        )

    gemini_client = genai.Client(api_key=cfg.api_key)

    gen_config_kwargs: dict[str, Any] = {
        "temperature":      temperature,
        "max_output_tokens": max_tokens,
    }
    
    # Phase 2A: Enable JSON mode with native response_mime_type
    if json_mode:
        gen_config_kwargs["response_mime_type"] = "application/json"
        if response_schema:
            gen_config_kwargs["response_schema"] = response_schema
    
    # Phase 2A: Disable thinking for structured generation
    # Gemini 2.5 Flash uses thinking_budget (0-24,576)
    # Setting to 0 disables internal reasoning, saving tokens
    thinking_disabled = True  # Always disable — thinking eats the budget in text mode too, not just JSON
    if thinking_disabled:
        gen_config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_budget=0
        )

    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    
    # Log the exact request being sent
    logger.debug(
        "Gemini API Request:\n"
        "  Model: %s\n"
        "  JSON Mode: %s\n"
        "  Thinking Disabled: %s\n"
        "  Temperature: %s\n"
        "  max_output_tokens: %s\n"
        "  response_mime_type: %s\n"
        "  response_schema: %s\n"
        "  Prompt length: %d chars",
        cfg.json_model if json_mode else cfg.model,
        json_mode,
        thinking_disabled,
        temperature,
        max_tokens,
        gen_config_kwargs.get("response_mime_type", "NOT_SET"),
        "DEFINED" if response_schema else "NOT_SET",
        len(full_prompt),
    )
    await _gemini_rate_gate()

    response = await gemini_client.aio.models.generate_content(
        model=cfg.json_model if json_mode else cfg.model,
        contents=full_prompt,
        config=genai_types.GenerateContentConfig(**gen_config_kwargs),
    )
    
    # Log raw response structure before parsing
    finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "NO_CANDIDATES"
    usage = response.usage_metadata
    
    prompt_tokens = _safe_int(getattr(usage, "prompt_token_count", 0))
    output_tokens = _safe_int(getattr(usage, "candidates_token_count", 0))
    thoughts_tokens = _safe_int(getattr(usage, "thoughts_token_count", 0))
    total_tokens = _safe_int(getattr(usage, "total_token_count", 0))
    
    # Phase 2A: Verify thinking was actually disabled
    if thinking_disabled and thoughts_tokens > 0:
        logger.warning(
            "⚠️  GEMINI IGNORED thinking_budget=0\n"
            "  Model: %s\n"
            "  Thoughts Tokens: %d (%.1f%% of total)\n"
            "  This is unexpected — thinking should be disabled for structured generation.\n"
            "  The SDK may not honor thinking_budget=0 correctly.",
            cfg.json_model if json_mode else cfg.model,
            thoughts_tokens,
            _safe_percent(thoughts_tokens, total_tokens),
        )
    elif thinking_disabled and thoughts_tokens == 0:
        logger.debug(
            "✓ Thinking successfully disabled (thoughts_tokens=0)"
        )
    
    # CRITICAL: Check for the contradiction (now with correct understanding)
    if finish_reason in ("MAX_TOKENS", "FinishReason.MAX_TOKENS"):
        # The limit is on TOTAL tokens, not output tokens
        # Gemini uses internal "thoughts" for JSON reasoning
        logger.error(
            "🚨 GEMINI TOTAL TOKEN LIMIT HIT 🚨\n"
            "  Finish Reason: %s\n"
            "  Total Tokens: %d (this is what hit the limit)\n"
            "  Breakdown:\n"
            "    - Prompt: %d tokens\n"
            "    - Thoughts (internal reasoning): %d tokens (%.1f%%)\n"
            "    - Output (actual response): %d tokens (%.1f%%)\n"
            "  Configured max_output_tokens: %d (misleading - limit is on TOTAL)\n"
            "  Model: %s\n"
            "  JSON Mode: %s\n"
            "  Thinking Disabled: %s\n"
            "\n"
            "ROOT CAUSE:\n"
            "  Gemini's real limit is ~4500 TOTAL tokens (prompt + thoughts + output).\n"
            "  In JSON mode, 'thoughts_token_count' consumes 80-90%% of the budget\n"
            "  for internal reasoning about JSON structure.\n"
            "\n"
            "SOLUTION:\n"
            "  Keep large generations on Groq where possible, or split them into smaller calls.\n"
            "  Gemini is unsuitable for outputs >1500 tokens in JSON mode.",
            finish_reason,
            total_tokens,
            prompt_tokens,
            thoughts_tokens,
            _safe_percent(thoughts_tokens, total_tokens),
            output_tokens,
            _safe_percent(output_tokens, total_tokens),
            max_tokens,
            cfg.json_model if json_mode else cfg.model,
            json_mode,
            thinking_disabled,
        )
    
    metadata = {
        "finish_reason": finish_reason,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "thoughts_tokens": thoughts_tokens,
        "total_tokens": total_tokens,
        "json_mode": json_mode,
        "thinking_disabled": thinking_disabled,
    }

    text = getattr(response, "text", None)
    if not text:
        raise AIResponseError("Gemini returned empty content")
    
    # Phase 2A: Enhanced response diagnostics
    logger.debug(
        "Gemini API Response:\n"
        "  Finish Reason: %s\n"
        "  Prompt Tokens: %d\n"
        "  Thoughts Tokens: %d (%.1f%% of total)\n"
        "  Output Tokens: %d (%.1f%% of total)\n"
        "  Total Tokens: %d\n"
        "  JSON Mode: %s\n"
        "  Thinking Disabled: %s\n"
        "  Response length: %d chars",
        finish_reason,
        prompt_tokens,
        thoughts_tokens,
        _safe_percent(thoughts_tokens, total_tokens),
        output_tokens,
        _safe_percent(output_tokens, total_tokens),
        total_tokens,
        json_mode,
        thinking_disabled,
        len(text),
    )
    
    return text, metadata


# ── Dispatch table ────────────────────────────────────────────────────────────

_PROVIDER_CALLERS = {
    ProviderName.GROQ:   _call_groq,
    ProviderName.MISTRAL: _call_groq,
    ProviderName.GEMINI: _call_gemini,
    ProviderName.AGENTROUTER: _call_groq,
}


async def _call_provider(
    cfg: ProviderConfig,
    *,
    prompt: str,
    system: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    response_schema: Optional[dict[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    caller = _PROVIDER_CALLERS.get(cfg.name)
    if caller is None:
        raise ProviderError(
            f"No caller implemented for provider {cfg.name}",
            provider=cfg.name.value,
        )
    
    # Pass response_schema only to providers that support it
    # Currently only Gemini supports response_schema
    if cfg.name == ProviderName.GEMINI:
        return await caller(
            cfg,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            # pyrefly: ignore [unexpected-keyword]
            response_schema=response_schema,
        )
    else:
        return await caller(
            cfg,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )


# ── Public API ─────────────────────────────────────────────────────────────────

async def generate_text(
    prompt:      str,
    system:      str  = "",
    temperature: float = 0.7,
    max_tokens:  int   = 2048,
) -> str:
    """
    Generate free-form text using the best available provider.

    Parameters
    ----------
    prompt:      User-facing prompt content.
    system:      Optional system / persona instruction.
    temperature: Sampling temperature (0.0–1.0).
    max_tokens:  Upper bound on response length.

    Returns
    -------
    Raw text string from the model.

    Raises
    ------
    ProviderError: When all providers fail.
    """
    result, _metadata = await _run_with_failover(
        prompt=prompt,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=False,
    )
    return result


async def generate_text_with_metadata(
    prompt:      str,
    system:      str  = "",
    temperature: float = 0.7,
    max_tokens:  int   = 2048,
) -> tuple[str, dict[str, Any]]:
    """
    Generate free-form text and return provider diagnostics.

    This preserves the public generate_text() API while giving production stages
    like sectioned narration enough observability to checkpoint and debug safely.
    """
    return await _run_with_failover(
        prompt=prompt,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=False,
    )


async def generate_json(
    prompt:      str,
    system:      str  = "",
    temperature: float = 0.4,
    max_tokens:  int   = 4096,
    response_schema: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Generate a JSON response and parse it into a dict.

    The client instructs the model to return valid JSON (via response_format
    or mime_type), then strips any residual markdown fences before parsing.
    
    Phase 2A: Now supports response_schema for strict JSON validation (Gemini only).

    Parameters
    ----------
    prompt:      User-facing prompt (should describe the expected JSON shape).
    system:      System instruction — include schema hints here.
    temperature: Lower values produce more deterministic structure.
    max_tokens:  Upper bound on response length.
    response_schema: Optional JSON schema for strict validation (dict format).

    Returns
    -------
    Parsed Python dict.

    Raises
    ------
    ProviderError:   When all providers fail.
    ValidationError: When the response cannot be parsed as JSON.
    """

    raw, metadata = await _run_with_failover(
        prompt=prompt,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
        response_schema=response_schema,
    )

    cleaned = _strip_markdown_fences(raw)
    
    # Check for truncation indicators
    finish_reason = metadata.get("finish_reason", "unknown")
    output_tokens = _safe_int(metadata.get("output_tokens", 0))
    provider = metadata.get("provider", "unknown")
    model = metadata.get("model", "unknown")
    json_mode_active = metadata.get("json_mode", True)
    thinking_disabled = metadata.get("thinking_disabled", False)
    
    is_truncated = (
        finish_reason in ("MAX_TOKENS", "length", "FinishReason.MAX_TOKENS")
        or cleaned.count("{") > cleaned.count("}")
        or cleaned.count("[") > cleaned.count("]")
        or cleaned.count('"') % 2 != 0
    )

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Enhanced error logging with metadata
        if is_truncated:
            logger.error(
                "JSON PARSE FAILED — TRUNCATION DETECTED\n"
                "Provider: %s\n"
                "Model: %s\n"
                "Finish Reason: %s\n"
                "Output Tokens: %d / %d\n"
                "JSON Mode: %s\n"
                "Thinking Disabled: %s\n"
                "Response Length: %d chars\n"
                "Unmatched Braces: { %d > } %d\n"
                "Last 500 chars:\n%s",
                provider,
                model,
                finish_reason,
                output_tokens,
                max_tokens,
                json_mode_active,
                thinking_disabled,
                len(cleaned),
                cleaned.count("{"),
                cleaned.count("}"),
                cleaned[-500:],
            )
        else:
            logger.error(
                "JSON PARSE FAILED — INVALID JSON\n"
                "Provider: %s\n"
                "Model: %s\n"
                "Finish Reason: %s\n"
                "JSON Mode: %s\n"
                "Thinking Disabled: %s\n"
                "Response Length: %d\n"
                "First 500 chars:\n%s",
                provider,
                model,
                finish_reason,
                json_mode_active,
                thinking_disabled,
                len(cleaned),
                cleaned[:500],
            )
        
        raise ValidationError(
            f"Response was not valid JSON: {exc}",
            raw=cleaned,
        ) from exc


# ── Failover engine ────────────────────────────────────────────────────────────

async def _run_with_failover(
    *,
    prompt:      str,
    system:      str,
    temperature: float,
    max_tokens:  int,
    json_mode:   bool,
    response_schema: Optional[dict[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    """
    Iterate through enabled providers in priority order.

    On any error deemed retryable (rate limit, timeout, server error),
    log a warning and try the next provider.

    On non-retryable errors (AuthenticationError, bad request), raise
    immediately — failover would not help.

    On a "successful" json_mode response that's actually truncated (some
    providers return this as a normal 200, not an exception — e.g. Mistral,
    unlike Groq which raises its own error on malformed JSON), treat it the
    same as a failure and advance to the next provider, rather than
    returning garbage that will fail JSON parsing downstream with no
    provider left to fall back to.

    Returns tuple of (content, metadata) where metadata contains:
    - finish_reason: why generation stopped
    - provider: which provider was used
    - model: which model was used
    - prompt_tokens, output_tokens, total_tokens: usage stats
    - json_mode: whether JSON mode was enabled
    - thinking_disabled: whether thinking was disabled (Gemini only)
    """
    providers = get_enabled_providers()
    if not providers:
        raise ProviderError(
            "No AI providers are configured. Set GROQ_API_KEY or MISTRAL_API_KEY or GEMINI_API_KEY.",
            provider="none",
        )

    last_exc: Exception = ProviderError("Failover exhausted — all providers failed.")

    for cfg in providers:
        for attempt in range(1, 3):
            t0 = time.monotonic()
            try:
                result, metadata = await _call_provider(
                    cfg,
                    prompt=prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                    response_schema=response_schema,
                )
                elapsed_ms = int((time.monotonic() - t0) * 1000)

                # Add provider info and latency to metadata
                metadata["provider"] = cfg.name.value
                metadata["model"] = cfg.json_model if json_mode else cfg.model
                metadata["latency_ms"] = elapsed_ms

                finish_reason = metadata.get("finish_reason", "unknown")
                metadata["latency_ms"] = elapsed_ms
                metadata["provider_attempt"] = attempt
                output_tokens = _safe_int(metadata.get("output_tokens", 0))
                prompt_tokens = _safe_int(metadata.get("prompt_tokens", 0))
                thoughts_tokens = _safe_int(metadata.get("thoughts_tokens", 0))
                total_tokens = _safe_int(metadata.get("total_tokens", 0))
                json_mode_active = metadata.get("json_mode", json_mode)
                thinking_disabled = metadata.get("thinking_disabled", False)

                # Check for truncation
                # For Gemini, the limit is on total_tokens, not output_tokens
                is_gemini = cfg.name == ProviderName.GEMINI
                is_truncated = finish_reason in ("MAX_TOKENS", "length", "FinishReason.MAX_TOKENS")

                if is_truncated:
                    if is_gemini:
                        logger.warning(
                            "⚠️  GEMINI TOTAL TOKEN LIMIT | provider=%s model=%s finish_reason=%s\n"
                            "  Total: %d tokens (limit: ~4500)\n"
                            "  Breakdown: prompt=%d + thoughts=%d (%.1f%%) + output=%d (%.1f%%)\n"
                            "  JSON Mode: %s | Thinking Disabled: %s",
                            cfg.name.value,
                            metadata["model"],
                            finish_reason,
                            total_tokens,
                            prompt_tokens,
                            thoughts_tokens,
                            _safe_percent(thoughts_tokens, total_tokens),
                            output_tokens,
                            _safe_percent(output_tokens, total_tokens),
                            json_mode_active,
                            thinking_disabled,
                        )
                    else:
                        token_usage_pct = _safe_percent(output_tokens, max_tokens)
                        logger.warning(
                            "⚠️  OUTPUT TRUNCATION | provider=%s model=%s finish_reason=%s output_tokens=%d "
                            "max_tokens=%d usage=%.1f%% prompt_tokens=%d json_mode=%s",
                            cfg.name.value,
                            metadata["model"],
                            finish_reason,
                            output_tokens,
                            max_tokens,
                            token_usage_pct,
                            prompt_tokens,
                            json_mode_active,
                        )

                    # A truncated JSON response is unusable content wearing a
                    # "success" costume — some providers (Mistral) don't raise
                    # an error for this the way Groq does, so without this
                    # check it would be returned as if it were good, and the
                    # failover chain would never reach the next provider.
                    if json_mode:
                        logger.warning(
                            "Provider %s returned truncated JSON — not accepting as a "
                            "successful result, advancing to next provider instead.",
                            cfg.name.value,
                        )
                        last_exc = AIResponseError(
                            f"{cfg.name.value} returned truncated JSON output (finish_reason={finish_reason})"
                        )
                        break  # same prompt/budget won't fix it on this provider — move on

                elif _safe_int(max_tokens) > 0 and _safe_int(output_tokens) > 0:
                    usage_ratio = _safe_int(output_tokens) / _safe_int(max_tokens)
                    if usage_ratio > 0.8:
                        token_usage_pct = _safe_percent(output_tokens, max_tokens)
                        logger.warning(
                            "⚠️  HIGH TOKEN USAGE | provider=%s model=%s output_tokens=%d max_tokens=%d "
                            "usage=%.1f%% (approaching limit) json_mode=%s",
                            cfg.name.value,
                            metadata["model"],
                            _safe_int(output_tokens),
                            max_tokens,
                            token_usage_pct,
                            json_mode_active,
                        )
                else:
                    # Success - log comprehensive diagnostics
                    token_usage_pct = _safe_percent(output_tokens, max_tokens)
                    safe_output = _safe_int(output_tokens)
                    safe_prompt = _safe_int(prompt_tokens)
                    safe_thoughts = _safe_int(thoughts_tokens)

                    log_parts = [
                        f"✓ AI call succeeded | provider={cfg.name.value} model={metadata['model']} mode={'json' if json_mode else 'text'} latency_ms={elapsed_ms}",
                        f"finish_reason={finish_reason} tokens={safe_output}/{max_tokens} ({token_usage_pct:.1f}%) prompt={safe_prompt}"
                    ]
                    if is_gemini:
                        log_parts.append(f"thoughts={safe_thoughts} thinking_disabled={thinking_disabled}")
                    logger.info(" ".join(log_parts))

                if not (is_truncated and json_mode):
                    return result, metadata

            except Exception as exc:  # noqa: BLE001
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                retryable = _is_retryable(exc)

                logger.warning(
                    "Provider %s failed | attempt=%d retryable=%s latency_ms=%d error=%s",
                    cfg.name.value,
                    attempt,
                    retryable,
                    elapsed_ms,
                    exc,
                )

                last_exc = exc

                if not retryable:
                    raise ProviderError(
                        f"Provider {cfg.name.value} returned a non-retryable error: {exc}",
                        provider=cfg.name.value,
                        cause=exc,
                    ) from exc

                if attempt == 1:
                    await asyncio.sleep(_retry_delay_seconds(exc, attempt))
                    continue

                break

    raise ProviderError(
        f"All providers failed. Last error: {last_exc}",
        provider="all",
        cause=last_exc,
    ) from last_exc