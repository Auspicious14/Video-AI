---
description: How to use, run, and update the Research Intelligence Agent.
---

# Workflow: Research Intelligence Agent

This workflow covers how to launch topic research, run verification tests, and extend the structured schemas/prompts.

## 1. Run Unit Tests to Validate Changes

// turbo-all
Run the automated test suite to ensure the schema parsing, 10-step repair engine, properties, and serializers function correctly:

```bash
.venv/bin/python -m unittest tests/test_research_agent.py
```

## 2. Generate Research via Python REPL

To run the Research Agent interactively and inspect output structure:

```bash
.venv/bin/python
```

Within the REPL:

```python
import asyncio
from services.ai.research import run_research, research_to_context

async def demo():
    # Make sure GROQ_API_KEY or GEMINI_API_KEY is set in your .env
    result = await run_research(
        topic="Role of tech in Nigerian agriculture",
        tone="educational",
        duration=30,
        platform="youtube_long"
    )
    print("Executive Summary:", result.executive_summary)
    print("\nVisual Opportunities:")
    for vo in result.visual_opportunities[:3]:
        print(f"  - [{vo.visual_type}] {vo.concept}")

asyncio.run(demo())
```

## 3. Extending the Research Output Schema

To add new data fields for downstream agents:

1. Open `services/ai/schemas.py`.
2. Add the field to the `ResearchResult` class with a default value (e.g. `list` or `Optional`) to ensure older cached items do not break.
3. Update the matching JSON structure in `services/ai/prompts/research.md`.
4. Update `services/ai/research.py`'s `_validate_and_repair` function to coerce or clean up inputs if needed.
