#!/usr/bin/env python3
"""
Gemini Truncation Diagnostic Suite

Investigates the contradiction:
- FinishReason.MAX_TOKENS at 672 tokens
- Configured max_output_tokens: 4500
- Usage: 14.9%

This should be impossible if the limit is truly 4500.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def experiment_a_plain_text():
    """
    Experiment A: Plain text generation (no JSON mode)
    
    Request exactly 1000 words of plain text.
    """
    from google import genai
    from google.genai import types as genai_types
    
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt = (
        "Write exactly 1000 words about the history of artificial intelligence. "
        "Do not use JSON. Write as plain prose paragraphs."
    )
    
    config = genai_types.GenerateContentConfig(
        temperature=0.7,
        max_output_tokens=4500,
    )
    
    logger.info("=" * 80)
    logger.info("EXPERIMENT A: Plain Text Generation")
    logger.info("=" * 80)
    logger.info("Model: gemini-2.5-flash")
    logger.info("Prompt: %s", prompt[:100] + "...")
    logger.info("Config: temperature=0.7, max_output_tokens=4500")
    logger.info("JSON mode: NO")
    logger.info("-" * 80)
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )
    
    # Log raw response structure
    logger.info("Raw response type: %s", type(response))
    logger.info("Response attributes: %s", dir(response))
    
    # Extract finish reason
    finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "NO_CANDIDATES"
    logger.info("Finish Reason: %s", finish_reason)
    
    # Extract usage metadata
    usage = response.usage_metadata
    logger.info("Usage Metadata: %s", usage)
    logger.info("  prompt_token_count: %s", getattr(usage, "prompt_token_count", "N/A"))
    logger.info("  candidates_token_count: %s", getattr(usage, "candidates_token_count", "N/A"))
    logger.info("  total_token_count: %s", getattr(usage, "total_token_count", "N/A"))
    
    # Get text
    text = getattr(response, "text", "")
    word_count = len(text.split())
    char_count = len(text)
    
    logger.info("Output Statistics:")
    logger.info("  Characters: %d", char_count)
    logger.info("  Words: %d", word_count)
    logger.info("  Estimated tokens (chars/4): %d", char_count // 4)
    
    logger.info("First 200 chars: %s", text[:200])
    logger.info("Last 200 chars: %s", text[-200:])
    
    return {
        "experiment": "A_plain_text",
        "model": "gemini-2.5-flash",
        "max_output_tokens": 4500,
        "json_mode": False,
        "finish_reason": finish_reason,
        "prompt_tokens": getattr(usage, "prompt_token_count", 0),
        "output_tokens": getattr(usage, "candidates_token_count", 0),
        "total_tokens": getattr(usage, "total_token_count", 0),
        "word_count": word_count,
        "char_count": char_count,
        "text_sample": text[:500],
    }


async def experiment_b_json_mode():
    """
    Experiment B: JSON mode generation
    
    Request the same 1000-word content as JSON.
    """
    from google import genai
    from google.genai import types as genai_types
    
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt = (
        "Write exactly 1000 words about the history of artificial intelligence. "
        "Return as JSON with this structure:\n"
        '{"title": "...", "content": "... (the 1000-word essay) ..."}\n'
        "Put the full 1000-word essay in the content field."
    )
    
    config = genai_types.GenerateContentConfig(
        temperature=0.7,
        max_output_tokens=4500,
        response_mime_type="application/json",
    )
    
    logger.info("=" * 80)
    logger.info("EXPERIMENT B: JSON Mode Generation")
    logger.info("=" * 80)
    logger.info("Model: gemini-2.5-flash")
    logger.info("Prompt: %s", prompt[:100] + "...")
    logger.info("Config: temperature=0.7, max_output_tokens=4500, response_mime_type=application/json")
    logger.info("JSON mode: YES")
    logger.info("-" * 80)
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )
    
    # Log raw response structure
    logger.info("Raw response type: %s", type(response))
    
    # Extract finish reason
    finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "NO_CANDIDATES"
    logger.info("Finish Reason: %s", finish_reason)
    
    # Extract usage metadata
    usage = response.usage_metadata
    logger.info("Usage Metadata: %s", usage)
    logger.info("  prompt_token_count: %s", getattr(usage, "prompt_token_count", "N/A"))
    logger.info("  candidates_token_count: %s", getattr(usage, "candidates_token_count", "N/A"))
    logger.info("  total_token_count: %s", getattr(usage, "total_token_count", "N/A"))
    
    # Get text
    text = getattr(response, "text", "")
    char_count = len(text)
    
    # Try to parse JSON to count words in content
    try:
        parsed = json.loads(text)
        content = parsed.get("content", "")
        word_count = len(content.split())
        logger.info("JSON parsed successfully")
        logger.info("  Content word count: %d", word_count)
    except json.JSONDecodeError as exc:
        word_count = 0
        logger.warning("JSON parse failed: %s", exc)
        logger.warning("Raw text: %s", text[:500])
    
    logger.info("Output Statistics:")
    logger.info("  Characters: %d", char_count)
    logger.info("  Estimated tokens (chars/4): %d", char_count // 4)
    
    logger.info("First 200 chars: %s", text[:200])
    logger.info("Last 200 chars: %s", text[-200:])
    
    return {
        "experiment": "B_json_mode",
        "model": "gemini-2.5-flash",
        "max_output_tokens": 4500,
        "json_mode": True,
        "finish_reason": finish_reason,
        "prompt_tokens": getattr(usage, "prompt_token_count", 0),
        "output_tokens": getattr(usage, "candidates_token_count", 0),
        "total_tokens": getattr(usage, "total_token_count", 0),
        "word_count": word_count,
        "char_count": char_count,
        "text_sample": text[:500],
        "json_valid": word_count > 0,
    }


async def experiment_c_json_narration_only():
    """
    Experiment C: JSON with only narration field
    
    Simulates DocumentaryScriptResult but minimal structure.
    """
    from google import genai
    from google.genai import types as genai_types
    
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt = (
        "Write exactly 1000 words about the history of artificial intelligence. "
        "Return as JSON with this minimal structure:\n"
        '{"narration": "... (the 1000-word essay) ..."}\n'
        "Put the full 1000-word essay in the narration field. No other fields."
    )
    
    config = genai_types.GenerateContentConfig(
        temperature=0.7,
        max_output_tokens=4500,
        response_mime_type="application/json",
    )
    
    logger.info("=" * 80)
    logger.info("EXPERIMENT C: JSON Narration Only")
    logger.info("=" * 80)
    logger.info("Model: gemini-2.5-flash")
    logger.info("Prompt: %s", prompt[:100] + "...")
    logger.info("Config: temperature=0.7, max_output_tokens=4500, response_mime_type=application/json")
    logger.info("JSON mode: YES (minimal structure)")
    logger.info("-" * 80)
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )
    
    # Extract finish reason
    finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "NO_CANDIDATES"
    logger.info("Finish Reason: %s", finish_reason)
    
    # Extract usage metadata
    usage = response.usage_metadata
    logger.info("Usage Metadata: %s", usage)
    logger.info("  prompt_token_count: %s", getattr(usage, "prompt_token_count", "N/A"))
    logger.info("  candidates_token_count: %s", getattr(usage, "candidates_token_count", "N/A"))
    logger.info("  total_token_count: %s", getattr(usage, "total_token_count", "N/A"))
    
    # Get text
    text = getattr(response, "text", "")
    char_count = len(text)
    
    # Try to parse JSON to count words in narration
    try:
        parsed = json.loads(text)
        narration = parsed.get("narration", "")
        word_count = len(narration.split())
        logger.info("JSON parsed successfully")
        logger.info("  Narration word count: %d", word_count)
    except json.JSONDecodeError as exc:
        word_count = 0
        logger.warning("JSON parse failed: %s", exc)
        logger.warning("Raw text: %s", text[:500])
    
    logger.info("Output Statistics:")
    logger.info("  Characters: %d", char_count)
    logger.info("  Estimated tokens (chars/4): %d", char_count // 4)
    
    logger.info("First 200 chars: %s", text[:200])
    logger.info("Last 200 chars: %s", text[-200:])
    
    return {
        "experiment": "C_narration_only",
        "model": "gemini-2.5-flash",
        "max_output_tokens": 4500,
        "json_mode": True,
        "finish_reason": finish_reason,
        "prompt_tokens": getattr(usage, "prompt_token_count", 0),
        "output_tokens": getattr(usage, "candidates_token_count", 0),
        "total_tokens": getattr(usage, "total_token_count", 0),
        "word_count": word_count,
        "char_count": char_count,
        "text_sample": text[:500],
        "json_valid": word_count > 0,
    }


async def experiment_d_documentary_script():
    """
    Experiment D: Actual DocumentaryScriptResult structure
    
    This simulates the real production scenario.
    """
    from google import genai
    from google.genai import types as genai_types
    
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt = """Write a 1000-word documentary script about artificial intelligence.

Return as JSON with this exact structure:
{
  "hook": "Opening hook (1 sentence)",
  "narration": "... (full 1000-word narration) ...",
  "sections": ["Introduction", "Body", "Conclusion"],
  "estimated_duration_seconds": 180,
  "source_notes": ["Note 1", "Note 2"]
}

Put the full 1000-word essay in the narration field."""
    
    config = genai_types.GenerateContentConfig(
        temperature=0.62,
        max_output_tokens=4500,
        response_mime_type="application/json",
    )
    
    logger.info("=" * 80)
    logger.info("EXPERIMENT D: DocumentaryScriptResult Structure")
    logger.info("=" * 80)
    logger.info("Model: gemini-2.5-flash")
    logger.info("Prompt: %s", prompt[:100] + "...")
    logger.info("Config: temperature=0.62, max_output_tokens=4500, response_mime_type=application/json")
    logger.info("JSON mode: YES (full DocumentaryScriptResult)")
    logger.info("-" * 80)
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )
    
    # Extract finish reason
    finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "NO_CANDIDATES"
    logger.info("Finish Reason: %s", finish_reason)
    
    # Extract usage metadata
    usage = response.usage_metadata
    logger.info("Usage Metadata: %s", usage)
    logger.info("  prompt_token_count: %s", getattr(usage, "prompt_token_count", "N/A"))
    logger.info("  candidates_token_count: %s", getattr(usage, "candidates_token_count", "N/A"))
    logger.info("  total_token_count: %s", getattr(usage, "total_token_count", "N/A"))
    
    # Get text
    text = getattr(response, "text", "")
    char_count = len(text)
    
    # Try to parse JSON
    try:
        parsed = json.loads(text)
        narration = parsed.get("narration", "")
        word_count = len(narration.split())
        has_hook = bool(parsed.get("hook"))
        has_sections = bool(parsed.get("sections"))
        logger.info("JSON parsed successfully")
        logger.info("  Has hook: %s", has_hook)
        logger.info("  Has sections: %s", has_sections)
        logger.info("  Narration word count: %d", word_count)
    except json.JSONDecodeError as exc:
        word_count = 0
        logger.warning("JSON parse failed: %s", exc)
        logger.warning("Raw text: %s", text[:500])
        logger.warning("Last 200 chars: %s", text[-200:])
    
    logger.info("Output Statistics:")
    logger.info("  Characters: %d", char_count)
    logger.info("  Estimated tokens (chars/4): %d", char_count // 4)
    
    return {
        "experiment": "D_documentary_script",
        "model": "gemini-2.5-flash",
        "max_output_tokens": 4500,
        "json_mode": True,
        "finish_reason": finish_reason,
        "prompt_tokens": getattr(usage, "prompt_token_count", 0),
        "output_tokens": getattr(usage, "candidates_token_count", 0),
        "total_tokens": getattr(usage, "total_token_count", 0),
        "word_count": word_count,
        "char_count": char_count,
        "text_sample": text[:500],
        "json_valid": word_count > 0,
    }


async def verify_client_behavior():
    """
    Verify that our client.py is correctly passing max_output_tokens.
    """
    logger.info("=" * 80)
    logger.info("VERIFICATION: Client Behavior")
    logger.info("=" * 80)
    
    from services.ai.client import generate_json
    
    # Simple test
    logger.info("Testing generate_json with max_tokens=4500")
    
    try:
        result = await generate_json(
            prompt="Return a JSON object with one field 'test' containing exactly 500 words about AI.",
            system="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=4500,
        )
        
        logger.info("Result type: %s", type(result))
        logger.info("Result keys: %s", result.keys() if isinstance(result, dict) else "NOT_A_DICT")
        
        return {
            "test": "client_verification",
            "success": True,
            "result_type": str(type(result)),
        }
        
    except Exception as exc:
        logger.error("Client test failed: %s", exc, exc_info=True)
        return {
            "test": "client_verification",
            "success": False,
            "error": str(exc),
        }


async def main():
    """Run all diagnostic experiments."""
    logger.info("╔" + "═" * 78 + "╗")
    logger.info("║" + " " * 20 + "GEMINI TRUNCATION DIAGNOSTICS" + " " * 29 + "║")
    logger.info("╚" + "═" * 78 + "╝")
    logger.info("")
    
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY not set")
        return
    
    results = []
    
    # Run experiments
    try:
        result_a = await experiment_a_plain_text()
        results.append(result_a)
    except Exception as exc:
        logger.error("Experiment A failed: %s", exc, exc_info=True)
        results.append({"experiment": "A_plain_text", "error": str(exc)})
    
    await asyncio.sleep(2)  # Rate limiting
    
    try:
        result_b = await experiment_b_json_mode()
        results.append(result_b)
    except Exception as exc:
        logger.error("Experiment B failed: %s", exc, exc_info=True)
        results.append({"experiment": "B_json_mode", "error": str(exc)})
    
    await asyncio.sleep(2)
    
    try:
        result_c = await experiment_c_json_narration_only()
        results.append(result_c)
    except Exception as exc:
        logger.error("Experiment C failed: %s", exc, exc_info=True)
        results.append({"experiment": "C_narration_only", "error": str(exc)})
    
    await asyncio.sleep(2)
    
    try:
        result_d = await experiment_d_documentary_script()
        results.append(result_d)
    except Exception as exc:
        logger.error("Experiment D failed: %s", exc, exc_info=True)
        results.append({"experiment": "D_documentary_script", "error": str(exc)})
    
    await asyncio.sleep(2)
    
    try:
        result_verify = await verify_client_behavior()
        results.append(result_verify)
    except Exception as exc:
        logger.error("Client verification failed: %s", exc, exc_info=True)
        results.append({"test": "client_verification", "error": str(exc)})
    
    # Summary
    logger.info("")
    logger.info("╔" + "═" * 78 + "╗")
    logger.info("║" + " " * 33 + "SUMMARY" + " " * 38 + "║")
    logger.info("╚" + "═" * 78 + "╝")
    logger.info("")
    
    for result in results:
        if "error" in result:
            logger.info("%s: ERROR - %s", result.get("experiment", result.get("test", "unknown")), result["error"])
        else:
            exp_name = result.get("experiment", result.get("test", "unknown"))
            logger.info("%s:", exp_name)
            logger.info("  Finish Reason: %s", result.get("finish_reason", "N/A"))
            logger.info("  Output Tokens: %s", result.get("output_tokens", "N/A"))
            logger.info("  Max Configured: %s", result.get("max_output_tokens", "N/A"))
            if result.get("output_tokens") and result.get("max_output_tokens"):
                usage_pct = (result["output_tokens"] / result["max_output_tokens"]) * 100
                logger.info("  Usage: %.1f%%", usage_pct)
            logger.info("  Word Count: %s", result.get("word_count", "N/A"))
            logger.info("  JSON Valid: %s", result.get("json_valid", "N/A"))
            logger.info("")
    
    # Save results
    output_file = Path("gemini_diagnostic_results.json")
    output_file.write_text(json.dumps(results, indent=2))
    logger.info("Results saved to: %s", output_file)


if __name__ == "__main__":
    asyncio.run(main())
