# LLM Orchestration Layer Audit

**Date**: 2026-07-26  
**Status**: 🔴 Critical — Requires Immediate Hardening

---

## TASK 1: Complete LLM Call Audit

### Studio Pipeline Agents (YouTube Documentary)

| Agent | Model | Max Tokens | Temperature | JSON? | Est. Output | Risk Level |
|-------|-------|------------|-------------|-------|-------------|------------|
| **topic_intelligence** | gemini-2.5-flash | 1800 | 0.35 | ✅ | ~800 | 🟢 LOW |
| **research** | gemini-2.5-flash | 4096 (default) | 0.7 | ✅ | ~2500 | 🟡 MEDIUM |
| **story_architect** | gemini-2.5-flash | 2200 | 0.42 | ✅ | ~1200 | 🟢 LOW |
| **script_writer** | gemini-2.5-flash | **DYNAMIC** | 0.62 | ✅ | **1500-4500** | 🔴 **HIGH** |
| **script_qa** | gemini-2.5-flash | 4800 | 0.24 | ✅ | **2500-4000** | 🔴 **HIGH** |
| **visual_planner** | gemini-2.5-flash | **DYNAMIC** | 0.38 | ✅ | **2000-5000** | 🔴 **HIGH** |
| **image_generation_plan** | gemini-2.5-flash | varies | 0.42 | ✅ | ~1500 | 🟡 MEDIUM |
| **voice_direction** | gemini-2.5-flash | 1600 | 0.32 | ✅ | ~600 | 🟢 LOW |
| **editing_plan** | gemini-2.5-flash | 3500 | 0.36 | ✅ | ~2000 | 🟡 MEDIUM |
| **thumbnail_strategy** | gemini-2.5-flash | 2000 | 0.45 | ✅ | ~800 | 🟢 LOW |
| **title_strategy** | gemini-2.5-flash | 1800 | 0.48 | ✅ | ~700 | 🟢 LOW |
| **youtube_seo** | gemini-2.5-flash | 2400 | 0.38 | ✅ | ~1200 | 🟢 LOW |
| **final_qa** | gemini-2.5-flash | 3000 | 0.28 | ✅ | ~1500 | 🟡 MEDIUM |

### Legacy Pipelines

| Agent | Model | Max Tokens | Temperature | JSON? | Est. Output | Risk Level |
|-------|-------|------------|-------------|-------|-------------|------------|
| **tiktok_script** | gemini-2.5-flash | 2048 | 0.7 | ✅ | ~800 | 🟢 LOW |
| **youtube_script** | gemini-2.5-flash | 3000 | 0.7 | ✅ | ~1500 | 🟡 MEDIUM |
| **title_agent** | gemini-2.5-flash | 1500 | 0.8 | ✅ | ~600 | 🟢 LOW |
| **thumbnail_agent** | gemini-2.5-flash | 2000 | 0.75 | ✅ | ~800 | 🟢 LOW |
| **seo_agent** | gemini-2.5-flash | 2000 | 0.6 | ✅ | ~900 | 🟢 LOW |
| **motion_brief** | gemini-2.5-flash | 1800 | 0.65 | ✅ | ~800 | 🟢 LOW |

### Media Pipeline

| Agent | Model | Max Tokens | Temperature | JSON? | Est. Output | Risk Level |
|-------|-------|------------|-------------|-------|-------------|------------|
| **media_planner** | gemini-2.5-flash | varies | 0.45 | ✅ | ~1200 | 🟡 MEDIUM |
| **trend_discovery** | gemini-2.5-flash | 1024 | 0.9 | ✅ | ~600 | 🟢 LOW |
| **trend_deduplicator** | gemini-2.5-flash | 1500 | 0.3 | ✅ | ~800 | 🟢 LOW |

---

## CRITICAL FINDINGS

### 🔴 HIGH RISK: Script Writer

**Problem**: Dynamic token budget for 180s documentary
```python
_script_token_budget(180) = (180 * 3 * 1.55) + 1200 = 2037 tokens
```

**Actual Need**: 700-word narration + JSON structure
- Narration: ~700 words × 1.33 tokens = ~931 tokens
- JSON overhead (hook, sections, source_notes): ~300 tokens
- **Total needed**: ~1230 tokens
- **Buffer for safety**: 1500-1800 tokens

**Current allocation**: 2037 tokens ✅ (ADEQUATE)

**BUT** — for 300s (5-minute) documentary:
```python
_script_token_budget(300) = (300 * 3 * 1.55) + 1200 = 2595 tokens
```

**Actual Need**: 1200-word narration
- Narration: ~1200 words × 1.33 tokens = ~1596 tokens
- JSON overhead: ~300 tokens
- **Total needed**: ~1896 tokens
- **Current allocation**: 2595 tokens ✅ (ADEQUATE)

**Root Issue**: Gemini's **max_output_tokens** is being set correctly, but:
1. No finish_reason inspection
2. No token usage logging
3. No pre-flight budget validation

---

### 🔴 HIGH RISK: Script QA

**Problem**: Reviews entire script + provides revised version

**Structure**:
```json
{
  "approved": bool,
  "score": float,
  "revised_script": {
    "hook": "...",
    "narration": "... 700-1200 words ...",
    "sections": [...],
    "source_notes": [...]
  },
  "issues": [...],
  "strengths": [...]
}
```

**Token Estimate**:
- Original script reference: ~300 tokens (context)
- Revised narration: ~1596 tokens (1200 words)
- JSON structure: ~400 tokens
- Issues/strengths: ~300 tokens
- **Total needed**: ~2596 tokens

**Current allocation**: 4800 tokens ✅ (ADEQUATE)

**BUT** — This is the **MOST EXPENSIVE** call in the pipeline!

---

### 🔴 HIGH RISK: Visual Planner

**Problem**: Large timeline array for long videos

**Structure**:
```json
{
  "visual_style": "...",
  "consistency_rules": [...],
  "timeline": [
    {
      "index": 0,
      "start_seconds": 0.0,
      "end_seconds": 5.0,
      "narration_reference": "...",
      "on_screen": "...",
      "asset_type": "...",
      "search_queries": [...],
      "generation_prompt": "...",
      "motion_direction": "...",
      "assets": [...]
    },
    // ... 40-60 items for 300s video
  ]
}
```

**Token Estimate (300s video)**:
- 60 visual beats × ~60 tokens each = ~3600 tokens
- Structure overhead: ~200 tokens
- **Total needed**: ~3800 tokens

**Current allocation**: DYNAMIC (not explicitly set) — defaults to 4096

**Risk**: For long documentaries, could easily exceed limits

---

## ROOT CAUSE ANALYSIS

### Primary Issue: No Finish Reason Visibility

**Current Code** (`client.py:143`):
```python
logger.info("finish_reason=%s", response.candidates[0].finish_reason)
logger.info("token_count=%s", response.usage_metadata)
```

**Problems**:
1. ✅ Finish reason IS being logged
2. ❌ But it's at INFO level — invisible in production
3. ❌ Not exposed to calling code
4. ❌ Not checked for MAX_TOKENS condition
5. ❌ No warning when approaching limits

**Result**: When Gemini hits max_tokens:
- Returns partial JSON
- Logs "finish_reason=MAX_TOKENS" (but nobody sees it)
- JSON parsing fails
- Agent retries with same parameters
- Fails again
- Pipeline aborts

---

### Secondary Issue: No JSON Repair Logic

**Current Retry Logic** (`agent_utils.py:40`):
```python
for attempt in range(1, attempts + 1):
    try:
        raw = await generate_json(...)
        return model.model_validate(raw)
    except Exception:
        # Retry with lower temperature + more tokens
        continue
```

**Problems**:
1. ❌ Always regenerates ENTIRE artifact
2. ❌ No attempt to repair malformed JSON
3. ❌ No detection of "partial but valid" content
4. ❌ Expensive for large outputs

**Better Approach**:
1. Detect truncation (unmatched `{`, unterminated strings)
2. If content is ~90% complete, repair JSON structure
3. Only regenerate if content itself is incomplete

---

### Tertiary Issue: No Pre-Flight Budget Check

**Current Flow**:
1. Call LLM with max_tokens=X
2. Hope it fits
3. If it doesn't, retry
4. If it still doesn't, fail

**Better Flow**:
1. Estimate prompt tokens (using tiktoken)
2. Estimate expected output tokens
3. Compare to provider limits
4. If approaching limit, warn or route to different provider
5. If exceeding limit, fail-fast with clear error

---

## PROVIDER TOKEN LIMITS

### Current Provider Configurations

| Provider | Model | Max Output Tokens | Max Total Tokens | Timeout |
|----------|-------|-------------------|------------------|---------|
| **Groq** | llama-3.3-70b-versatile | 8192 | 32768 | 45s |
| **Gemini** | gemini-2.5-flash | **8192** | **1M** | 60s |
| **OpenAI** | gpt-4o-mini | 16384 | 128000 | 45s |

### Real-World Limits

**Gemini's Advertised Limits**:
- Max output tokens: 8192
- Max total tokens: 1M context

**Gemini's Real Behavior**:
- Often stops at ~2000-4000 tokens for JSON
- Finish reason: MAX_TOKENS
- Even when max_output_tokens=8192 is set

**Hypothesis**: Gemini's JSON mode has internal token limit lower than advertised

---

## SOLUTION ARCHITECTURE

### Phase 1: Visibility (Immediate)

1. **Expose finish reasons in generate_json()**
   - Return tuple: `(data, metadata)`
   - Metadata includes: finish_reason, token_usage, provider
   - Log at WARNING level when finish_reason != STOP

2. **Add token usage to all logs**
   - Log prompt tokens (estimated)
   - Log output tokens (actual)
   - Log percentage of max_output_tokens used

3. **Add budget warnings**
   - Warn when >80% of max_output_tokens used
   - Error when >95% used (approaching truncation)

### Phase 2: Repair Logic (High Priority)

1. **Implement JSON repair in agent_utils.py**
   ```python
   def attempt_json_repair(raw_text: str) -> dict | None:
       # Try to complete unfinished JSON
       # Fix unterminated strings
       # Add missing closing braces
       # Return repaired dict or None if unrepairable
   ```

2. **Smart retry in generate_structured_artifact()**
   ```python
   if attempt == 1 and is_truncated(raw):
       repaired = attempt_json_repair(raw)
       if repaired:
           return model.model_validate(repaired)
   # Only regenerate if repair failed
   ```

### Phase 3: Budget Management (Medium Priority)

1. **Add token estimation**
   ```python
   def estimate_tokens(text: str) -> int:
       # Use tiktoken for accurate estimation
       return len(enc.encode(text))
   ```

2. **Pre-flight budget check**
   ```python
   prompt_tokens = estimate_tokens(prompt + system)
   if prompt_tokens + max_tokens > provider_limit * 0.9:
       raise BudgetExceededError(...)
   ```

3. **Provider-specific limits in providers.py**
   ```python
   @dataclass
   class ProviderConfig:
       max_output_tokens: int
       max_total_tokens: int
       safe_output_tokens: int  # Conservative limit (80% of max)
   ```

### Phase 4: Provider Routing (Low Priority)

1. **Route large generations to OpenAI**
   - If estimated_output > 4000 tokens → prefer OpenAI
   - Gemini for small/medium generations
   - Groq for speed-critical generations

2. **Configurable routing rules**
   ```python
   ROUTING_RULES = {
       "script_writer": "prefer_openai_if_duration_gt_240",
       "script_qa": "prefer_openai",
       "visual_planner": "prefer_openai_if_beats_gt_40",
   }
   ```

---

## IMPLEMENTATION PRIORITY

### P0 (Critical — Do Now)
- ✅ Expose finish_reason in generate_json()
- ✅ Log token usage at WARNING level for truncation
- ✅ Implement basic JSON repair logic
- ✅ Add safe token budgets to ProviderConfig

### P1 (High — This Week)
- Implement pre-flight budget checking
- Add tiktoken-based token estimation
- Route script_qa to OpenAI automatically

### P2 (Medium — This Month)
- Implement full provider routing logic
- Add adaptive token budgeting
- Split DocumentaryScriptResult if needed

### P3 (Low — Future)
- ML-based token estimation
- Dynamic provider selection based on latency
- Cost-optimized routing

---

## ESTIMATED TOKEN SAVINGS

### Current State (Failed Run)
- Attempt 1: script_writer → 2595 tokens → **TRUNCATED**
- Attempt 2: script_writer → 2595 tokens → **TRUNCATED** (regenerate all)
- **Total wasted**: ~5190 tokens

### With JSON Repair
- Attempt 1: script_writer → 2595 tokens → TRUNCATED
- Attempt 2: JSON repair → 0 tokens (free)
- **Savings**: ~2595 tokens (50%)

### With Pre-Flight Routing
- Pre-flight check → route to OpenAI
- Attempt 1: script_writer → 2595 tokens → **SUCCESS**
- **Savings**: 100% success rate, 1 attempt only

---

## CONFIDENCE LEVEL

### After Phase 1 (Visibility)
**Confidence**: 40%
- We'll see WHY failures happen
- But won't prevent them

### After Phase 2 (Repair)
**Confidence**: 70%
- Most truncated JSON will be repairable
- Prevents expensive regenerations
- But doesn't prevent truncation

### After Phase 3 (Budget Management)
**Confidence**: 90%
- Pre-flight checks prevent truncation
- Smart routing to capable providers
- Predictable token usage

### After Phase 4 (Full Routing)
**Confidence**: 95%
- Provider selection optimized
- Cost and latency balanced
- Comprehensive observability

---

## NEXT STEPS

1. Implement Phase 1 (visibility) immediately
2. Test with a 300s documentary
3. Verify finish_reason logging works
4. Implement Phase 2 (repair) if truncation still occurs
5. Consider adding OpenAI as fallback for large generations
