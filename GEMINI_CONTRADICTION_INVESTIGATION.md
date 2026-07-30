# Gemini Truncation Contradiction Investigation

**Date**: 2026-07-26  
**Status**: 🔍 INVESTIGATION IN PROGRESS

---

## The Contradiction

Current production logs show:

```
FinishReason.MAX_TOKENS
Output Tokens: 672
Configured Max Tokens: 4500
Usage: 14.9%
```

**This is mathematically impossible** if the configured limit is being honored.

---

## Hypotheses to Test

### Hypothesis 1: SDK is Ignoring max_output_tokens
**Test**: Log the exact request payload before API call  
**Evidence needed**: Confirm max_output_tokens is present in GenerateContentConfig  
**Diagnostic**: Added detailed request logging to _call_gemini()

### Hypothesis 2: JSON Mode Has Lower Internal Limit
**Test**: Compare plain text vs JSON generation with same max_tokens  
**Evidence needed**: Show finish_reason differs between modes  
**Diagnostic**: Experiments A (plain text) vs B (JSON mode)

### Hypothesis 3: Token Counting is Wrong
**Test**: Compare output_tokens reported vs actual character count  
**Evidence needed**: Show tokens don't match expected ratio (~4 chars/token)  
**Diagnostic**: Log both token count and character count in all experiments

### Hypothesis 4: Total Context Limit is Hit
**Test**: Check if prompt_tokens + output_tokens exceeds some threshold  
**Evidence needed**: Show total_token_count near a documented limit  
**Diagnostic**: Log all three token counts in experiments

### Hypothesis 5: Finish Reason is Misreported
**Test**: Verify response is actually complete despite MAX_TOKENS  
**Evidence needed**: JSON is valid and complete at 672 tokens  
**Diagnostic**: Examine actual response content for truncation

### Hypothesis 6: Model-Specific Behavior
**Test**: Verify exact model name being used  
**Evidence needed**: Confirm gemini-2.5-flash vs gemini-2.0-flash-exp, etc.  
**Diagnostic**: Log model name in every request

---

## Diagnostic Experiments

### Experiment A: Plain Text (Control)
**Goal**: Establish baseline behavior without JSON mode

```python
Request: "Write exactly 1000 words about AI history"
Config: max_output_tokens=4500, NO JSON mode
Expected: ~1000 words, finish_reason=STOP
```

**Measures**:
- finish_reason
- output_tokens
- word_count
- Whether 1000 words are actually generated

### Experiment B: JSON Mode (Test Case)
**Goal**: Test if JSON mode has different limits

```python
Request: Same 1000-word content in JSON
Config: max_output_tokens=4500, response_mime_type="application/json"
Expected: ~1000 words, finish_reason=STOP (if Hypothesis 2 is false)
```

**Measures**:
- finish_reason (expect STOP, but may be MAX_TOKENS)
- output_tokens vs Experiment A
- Whether content is truncated

### Experiment C: Minimal JSON Structure
**Goal**: Test if structure complexity matters

```python
Request: {"narration": "... 1000 words ..."}
Config: max_output_tokens=4500, JSON mode
Expected: Reveal if structure affects truncation
```

### Experiment D: DocumentaryScriptResult (Production)
**Goal**: Reproduce actual production scenario

```python
Request: Full DocumentaryScriptResult structure
Config: max_output_tokens=4500, temperature=0.62, JSON mode
Expected: Reproduce the 672-token truncation
```

---

## Evidence Collection Checklist

- [ ] Exact request payload logged (before API call)
- [ ] Exact response object logged (raw structure)
- [ ] Model name confirmed (gemini-2.5-flash vs others)
- [ ] finish_reason for plain text documented
- [ ] finish_reason for JSON documented
- [ ] output_tokens in both modes compared
- [ ] Character count vs token count ratio verified
- [ ] Total context usage analyzed
- [ ] JSON validity at truncation point checked
- [ ] Contradiction reproduced in controlled test

---

## Implementation

### Enhanced Logging in client.py

**Before API call**:
```python
logger.debug(
    "Gemini API Request:\n"
    "  Model: %s\n"
    "  JSON Mode: %s\n"
    "  max_output_tokens: %s\n"
    "  response_mime_type: %s",
    model, json_mode, max_tokens, mime_type
)
```

**After API call**:
```python
logger.debug(
    "Gemini API Response:\n"
    "  Finish Reason: %s\n"
    "  Output Tokens: %d\n"
    "  Response length: %d chars",
    finish_reason, output_tokens, len(text)
)
```

**Contradiction Detection**:
```python
if finish_reason == "MAX_TOKENS" and output_tokens < max_tokens:
    logger.error("🚨 CONTRADICTION DETECTED 🚨")
```

### Diagnostic Script

**File**: `diagnose_gemini_truncation.py`

**Experiments**:
1. Plain text generation (1000 words)
2. JSON mode generation (same content)
3. Minimal JSON structure
4. DocumentaryScriptResult structure
5. Client behavior verification

**Output**: `gemini_diagnostic_results.json`

---

## Expected Outcomes

### If Hypothesis 1 is True (SDK ignoring max_output_tokens)
**Evidence**: Request logs show max_output_tokens NOT in payload OR response ignores it  
**Action**: File SDK bug report, switch to different SDK or API method  

### If Hypothesis 2 is True (JSON mode has lower limit)
**Evidence**: Experiment A completes, Experiment B truncates at same token budget  
**Action**: Document real JSON limit, adjust token budgets, route large JSON to OpenAI  

### If Hypothesis 3 is True (Token counting wrong)
**Evidence**: output_tokens doesn't match character count ratio  
**Action**: Use character-based estimation instead of token counts  

### If Hypothesis 4 is True (Total context limit)
**Evidence**: prompt_tokens + output_tokens near a threshold (e.g., 8192)  
**Action**: Reduce prompt size or split into multiple calls  

### If Hypothesis 5 is True (Finish reason misreported)
**Evidence**: Response is complete and valid despite MAX_TOKENS  
**Action**: Ignore finish_reason, validate JSON instead  

### If Hypothesis 6 is True (Model-specific)
**Evidence**: Different model versions behave differently  
**Action**: Document per-model limits, select appropriate model  

---

## How to Run Diagnostics

```bash
# Set API key
export GEMINI_API_KEY=your_key_here

# Run diagnostic suite
python diagnose_gemini_truncation.py

# Review results
cat gemini_diagnostic_results.json
```

**Expected runtime**: ~30 seconds (4 experiments + 2s rate limiting between each)

---

## Success Criteria

**Investigation is complete when**:
1. The contradiction is reproduced in a controlled test
2. The root cause is identified with evidence (not assumptions)
3. The true limit is documented with proof
4. A fix or workaround is implemented
5. The fix is verified to resolve the original failure

**Investigation is inconclusive if**:
- Cannot reproduce the contradiction
- Experiments show inconsistent results
- SDK behavior is undocumented and unpredictable

In that case, recommendation is to **route all large JSON generations to OpenAI** as the reliable fallback.

---

## Next Steps

1. ✅ Enhanced logging added to client.py
2. ✅ Diagnostic script created
3. ⏳ Run diagnostic experiments (requires API key and quota)
4. ⏳ Analyze results
5. ⏳ Document findings
6. ⏳ Implement fix or workaround
7. ⏳ Verify fix resolves production issue

---

## Production Impact

**Current state**: Pipeline aborts when Gemini hits 672 tokens  
**With diagnostics**: We'll know WHY it happens  
**After fix**: Either adjust limits or route to OpenAI

**Risk**: If Gemini is fundamentally unreliable for large JSON, we need provider routing (Phase 3 from hardening plan).
