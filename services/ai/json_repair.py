"""
JSON repair utilities for handling truncated LLM responses.

When an LLM response is truncated due to max_tokens, the JSON may be incomplete.
This module attempts to repair common truncation patterns without regenerating
the entire response.

Repair strategies:
1. Close unterminated strings
2. Add missing closing braces/brackets
3. Remove trailing commas
4. Complete partial field values
"""

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


def attempt_json_repair(raw_text: str) -> Optional[dict[str, Any]]:
    """
    Attempt to repair truncated or malformed JSON.
    
    Parameters
    ----------
    raw_text: The raw JSON string that failed to parse
    
    Returns
    -------
    Repaired dict if successful, None if unrepairable
    
    Repair Strategies
    -----------------
    1. Simple truncation: Add missing closing braces
    2. Unterminated string: Close the string properly
    3. Trailing comma: Remove before closing
    4. Partial array: Close the array
    """
    if not raw_text or not raw_text.strip():
        return None
    
    cleaned = raw_text.strip()
    
    # Try parsing as-is first (maybe it's actually valid)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Strategy 1: Simple brace/bracket balancing
    repaired = _balance_braces(cleaned)
    if repaired:
        return repaired
    
    # Strategy 2: Fix unterminated strings
    repaired = _fix_unterminated_strings(cleaned)
    if repaired:
        return repaired
    
    # Strategy 3: Aggressive truncation repair
    repaired = _aggressive_truncation_repair(cleaned)
    if repaired:
        return repaired
    
    # Could not repair
    logger.warning("JSON repair failed — all strategies exhausted")
    return None


def _balance_braces(text: str) -> Optional[dict[str, Any]]:
    """
    Balance unmatched braces and brackets.
    
    Example:
        Input:  {"key": "value", "nested": {"inner"
        Output: {"key": "value", "nested": {"inner": ""}}
    """
    open_braces = text.count("{")
    close_braces = text.count("}")
    open_brackets = text.count("[")
    close_brackets = text.count("]")
    
    # Check if only slightly unbalanced (good candidate for repair)
    brace_diff = open_braces - close_braces
    bracket_diff = open_brackets - close_brackets
    
    if brace_diff > 5 or bracket_diff > 5:
        # Too damaged — likely not just truncation
        return None
    
    repaired = text
    
    # Remove any trailing commas before we add closers
    repaired = re.sub(r',\s*$', '', repaired)
    
    # Check if we're in the middle of a string
    quote_count = repaired.count('"') - repaired.count('\\"')
    if quote_count % 2 != 0:
        # Unterminated string — close it
        repaired += '"'
    
    # Add missing closing brackets (arrays close before objects)
    if bracket_diff > 0:
        repaired += "]" * bracket_diff
    
    # Add missing closing braces
    if brace_diff > 0:
        repaired += "}" * brace_diff
    
    try:
        parsed = json.loads(repaired)
        logger.info("✓ JSON repair successful — balanced braces/brackets")
        return parsed
    except json.JSONDecodeError as exc:
        logger.debug("Brace balancing failed: %s", exc)
        return None


def _fix_unterminated_strings(text: str) -> Optional[dict[str, Any]]:
    """
    Fix unterminated string values.
    
    Example:
        Input:  {"key": "value", "description": "This is a long
        Output: {"key": "value", "description": "This is a long"}
    """
    # Count quotes (excluding escaped quotes)
    quote_count = text.count('"') - text.count('\\"')
    
    if quote_count % 2 == 0:
        # Quotes are balanced — not a string termination issue
        return None
    
    repaired = text + '"'
    
    # Now balance braces
    open_braces = repaired.count("{")
    close_braces = repaired.count("}")
    open_brackets = repaired.count("[")
    close_brackets = repaired.count("]")
    
    # Remove trailing comma if present
    repaired = re.sub(r',\s*$', '', repaired)
    
    # Close arrays first, then objects
    if open_brackets > close_brackets:
        repaired += "]" * (open_brackets - close_brackets)
    
    if open_braces > close_braces:
        repaired += "}" * (open_braces - close_braces)
    
    try:
        parsed = json.loads(repaired)
        logger.info("✓ JSON repair successful — fixed unterminated string")
        return parsed
    except json.JSONDecodeError as exc:
        logger.debug("String termination fix failed: %s", exc)
        return None


def _aggressive_truncation_repair(text: str) -> Optional[dict[str, Any]]:
    """
    Aggressively repair truncated JSON by removing incomplete fields.
    
    This is a last-resort strategy that discards the incomplete trailing content.
    
    Example:
        Input:  {"key": "value", "long_text": "This is trunca
        Output: {"key": "value"}
    """
    # Find the last complete field before truncation
    # Strategy: Work backwards to find last complete key-value pair
    
    # Remove anything after the last complete value
    patterns_to_try = [
        # Last complete string value
        r'(.*"[^"]+"\s*:\s*"[^"]*")\s*,?\s*[^}]*$',
        # Last complete number value
        r'(.*"[^"]+"\s*:\s*\d+)\s*,?\s*[^}]*$',
        # Last complete boolean value
        r'(.*"[^"]+"\s*:\s*(?:true|false))\s*,?\s*[^}]*$',
        # Last complete null value
        r'(.*"[^"]+"\s*:\s*null)\s*,?\s*[^}]*$',
        # Last complete array
        r'(.*"[^"]+"\s*:\s*\[[^\]]*\])\s*,?\s*[^}]*$',
        # Last complete object
        r'(.*"[^"]+"\s*:\s*\{[^}]*\})\s*,?\s*[^}]*$',
    ]
    
    for pattern in patterns_to_try:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            truncated = match.group(1)
            
            # Remove trailing comma
            truncated = re.sub(r',\s*$', '', truncated)
            
            # Balance braces
            open_braces = truncated.count("{")
            close_braces = truncated.count("}")
            open_brackets = truncated.count("[")
            close_brackets = truncated.count("]")
            
            if open_brackets > close_brackets:
                truncated += "]" * (open_brackets - close_brackets)
            
            if open_braces > close_braces:
                truncated += "}" * (open_braces - close_braces)
            
            try:
                parsed = json.loads(truncated)
                logger.warning(
                    "⚠️  JSON repair successful — discarded truncated content "
                    "(original: %d chars, repaired: %d chars)",
                    len(text),
                    len(truncated),
                )
                return parsed
            except json.JSONDecodeError:
                continue
    
    return None


def is_likely_truncated(text: str) -> bool:
    """
    Check if text shows signs of truncation.
    
    Returns
    -------
    True if the text is likely truncated
    """
    if not text:
        return False
    
    # Check for unbalanced structure
    open_braces = text.count("{")
    close_braces = text.count("}")
    open_brackets = text.count("[")
    close_brackets = text.count("]")
    
    if open_braces != close_braces or open_brackets != close_brackets:
        return True
    
    # Check for unterminated strings
    quote_count = text.count('"') - text.count('\\"')
    if quote_count % 2 != 0:
        return True
    
    # Check if ends mid-word or mid-syntax
    text_stripped = text.rstrip()
    if not text_stripped:
        return False
    
    last_char = text_stripped[-1]
    if last_char not in ('}', ']', '"', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'e', 'l'):
        # Ends with something that's not a valid JSON terminator
        return True
    
    return False
