"""
services/ai/providers.py — Provider configuration and registry.

Only this module (and client.py) know about specific AI providers.
Business logic must never import from here directly.

Provider Priority (failover order):
  1. Groq  — fast, generous free tier
  2. Mistral — fast, generous free tier
  3. Gemini — Google, reliable fallback
  4. Exception raised

Each provider exposes an OpenAI-compatible SDK interface.
Gemini uses the google-genai SDK via a compatibility shim.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ── Provider identity ─────────────────────────────────────────────────────────

class ProviderName(str, Enum):
    GROQ   = "groq"
    MISTRAL = "mistral"
    GEMINI = "gemini"
    AGENTROUTER = "agentrouter" 
    OPENAI = "openai"


# ── Provider descriptor ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProviderConfig:
    """
    Immutable descriptor for a single AI provider.

    Fields
    ------
    name:         Human-readable identifier used in logs.
    api_key:      Secret loaded from the environment.
    base_url:     OpenAI-compatible endpoint (None → use provider SDK).
    model:        Default model name for this provider.
    json_model:   Model to prefer when structured JSON output is required.
    timeout:      Per-request timeout in seconds.
    max_output_tokens: Advertised max output tokens for this provider.
    max_total_tokens:  Advertised max total tokens (prompt + output).
    safe_output_tokens: Conservative output limit (80% of max) to avoid truncation.
    enabled:      False when the API key is absent — provider is skipped.
    """

    name:       ProviderName
    api_key:    str
    base_url:   Optional[str]
    model:      str
    json_model: str
    timeout:    float = 30.0
    max_output_tokens: int = 4096
    max_total_tokens: int = 32768
    safe_output_tokens: int = field(init=False)
    enabled:    bool  = field(init=False)

    def __post_init__(self) -> None:
        # frozen=True means we must use object.__setattr__ to initialise
        # computed attributes after __init__.
        object.__setattr__(self, "enabled", bool(self.api_key))
        object.__setattr__(self, "safe_output_tokens", int(self.max_output_tokens * 0.8))
        
        if not self.enabled:
            logger.debug("Provider %s disabled — API key not set", self.name)
        else:
            logger.debug(
                "Provider %s enabled | max_output=%d safe_output=%d max_total=%d",
                self.name,
                self.max_output_tokens,
                self.safe_output_tokens,
                self.max_total_tokens,
            )


# ── Provider registry ─────────────────────────────────────────────────────────

def _load_provider_order() -> list[ProviderName]:
    """
    Reads PROVIDER_ORDER from the environment.

    Format: comma-separated names, e.g. "groq,gemini"
    Defaults to groq → gemini.
    """
    raw = os.getenv("PROVIDER_ORDER", "groq,mistral,gemini,agentrouter")
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    order: list[ProviderName] = []
    for n in names:
        try:
            order.append(ProviderName(n))
        except ValueError:
            logger.warning("Unknown provider in PROVIDER_ORDER: %r — ignored", n)
    return order or [ProviderName.GROQ, ProviderName.MISTRAL, ProviderName.GEMINI, ProviderName.AGENTROUTER]


def build_provider_registry() -> dict[ProviderName, ProviderConfig]:
    """
    Constructs the provider registry from environment variables.
    Called once at import time.
    """
    return {
        ProviderName.GROQ: ProviderConfig(
            name       = ProviderName.GROQ,
            api_key    = os.getenv("GROQ_API_KEY", ""),
            base_url   = "https://api.groq.com/openai/v1",
            model      = "openai/gpt-oss-120b",
            json_model = "openai/gpt-oss-120b",
            timeout    = 45.0,
            max_output_tokens = 8192,
            max_total_tokens = 32768,
        ),
        ProviderName.MISTRAL: ProviderConfig(
            name       = ProviderName.MISTRAL,
            api_key    = os.getenv("MISTRAL_API_KEY", ""),
            base_url   = "https://api.mistral.ai/v1",
            model      = "mistral-small-latest",
            json_model = "mistral-small-latest",
            timeout    = 45.0,
            max_output_tokens = 4096,
            max_total_tokens = 32000,
        ),
        ProviderName.GEMINI: ProviderConfig(
            name       = ProviderName.GEMINI,
            api_key    = os.getenv("GEMINI_API_KEY", ""),
            base_url   = None,          # uses google-genai SDK directly
            model      = "gemini-2.5-flash",
            json_model = "gemini-2.5-flash",
            timeout    = 60.0,
            # Note: Gemini advertises 8192 but appears to have lower internal limits for JSON mode
            # Conservative allocation based on observed behavior
            max_output_tokens = 8192,
            max_total_tokens = 1000000,  # 1M context window
        ),
        ProviderName.AGENTROUTER: ProviderConfig(
            name       = ProviderName.AGENTROUTER,
            api_key    = os.getenv("AGENTROUTER_API_KEY", ""),
            base_url   = "https://agentrouter.org/v1",
            model      = "gpt-5.6",  # confirm the exact model string in your AgentRouter dashboard
            json_model = "gpt-5.6",
            timeout    = 45.0,
            max_output_tokens = 4096,
            max_total_tokens = 32000,
        ),
        ProviderName.OPENAI: ProviderConfig(
            name       = ProviderName.OPENAI,
            api_key    = os.getenv("OPENAI_API_KEY", ""),
            base_url   = None,          # official OpenAI endpoint
            model      = "gpt-4o-mini",
            json_model = "gpt-4o-mini",
            timeout    = 45.0,
            max_output_tokens = 16384,
            max_total_tokens = 128000,
        ),
    }


# Singleton registry — imported by client.py
PROVIDER_REGISTRY: dict[ProviderName, ProviderConfig] = build_provider_registry()
PROVIDER_ORDER: list[ProviderName] = _load_provider_order()

_active_chain = [
    name.value for name in PROVIDER_ORDER
    if name in PROVIDER_REGISTRY and PROVIDER_REGISTRY[name].enabled
]
logger.info(
    "[Providers] Active chain: %s (configured order: %s)",
    " -> ".join(_active_chain) or "NONE ENABLED — check .env API keys",
    ",".join(n.value for n in PROVIDER_ORDER),
)


def get_enabled_providers() -> list[ProviderConfig]:
    """Return providers in priority order, filtering out disabled ones."""
    enabled = [
        PROVIDER_REGISTRY[name]
        for name in PROVIDER_ORDER
        if name in PROVIDER_REGISTRY and PROVIDER_REGISTRY[name].enabled
    ]
    if not enabled:
        logger.warning("No AI providers are enabled — check API keys in .env")
    return enabled
