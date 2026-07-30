"""
services/ai — VideoAI Unified AI Layer v2

Public surface area
-------------------
    from services.ai import generate_text, generate_json
    from services.ai import run_research, run_script_agent
    from services.ai import run_title_agent, run_thumbnail_agent, run_seo_agent
    from services.ai.schemas import ScriptResult, ResearchResult, ...
    from services.ai.exceptions import ProviderError, ValidationError, ...

Architecture
------------
    client.py      — Unified AI client (failover: Groq → Gemini)
    providers.py   — Provider registry (loaded from env vars)
    prompts.py     — Template loader (services/ai/prompts/*.md)
    schemas.py     — Pydantic models for all AI responses
    exceptions.py  — Custom exception hierarchy

    research.py    — Research Agent
    scripting.py   — Script Agent (TikTok / YouTube)
    title.py       — Title Agent
    thumbnail.py   — Thumbnail Agent
    seo.py         — SEO Agent
"""

from services.ai.client import generate_json, generate_text
from services.ai.exceptions import (
    AIError,
    AIResponseError,
    PromptError,
    ProviderError,
    ValidationError,
)
from services.ai.research import (
    research_hooks_summary,
    research_risks_summary,
    research_to_context,
    research_to_summary,
    run_research,
)
from services.ai.scripting import run_script_agent
from services.ai.seo import run_seo_agent
from services.ai.thumbnail import run_thumbnail_agent
from services.ai.title import run_title_agent

__all__ = [
    # Client
    "generate_text",
    "generate_json",
    # Agents
    "run_research",
    "run_script_agent",
    "run_title_agent",
    "run_thumbnail_agent",
    "run_seo_agent",
    # Formatters
    "research_to_summary",
    "research_to_context",
    "research_hooks_summary",
    "research_risks_summary",
    # Exceptions
    "AIError",
    "ProviderError",
    "ValidationError",
    "PromptError",
    "AIResponseError",
]
