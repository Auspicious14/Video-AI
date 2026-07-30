# Hotfix: Voice Direction Agent Parameter Error

**Date**: 2026-07-26 22:32  
**Severity**: HIGH (production blocker)  
**Status**: ✅ FIXED

---

## Error

```
TypeError: run_voice_direction_agent() got an unexpected keyword argument 'script_qa'
```

**Location**: `services/ai/studio/pipeline.py:489`

---

## Root Cause

Voice direction agent call was using old Phase 0 parameters instead of Phase 1 context architecture.

**Old call** (line 489):
```python
factory=lambda: run_voice_direction_agent(
    script_qa=script_qa, 
    requested_voice_id=req.voice_id
)
```

**Actual signature** (voice_director.py:13):
```python
async def run_voice_direction_agent(
    *,
    context: VoiceDirectionContext,
) -> VoiceDirectionResult:
```

**Mismatch**: Function expects `context`, but was called with `script_qa` and `requested_voice_id`.

---

## Fix

**File**: `services/ai/studio/pipeline.py`  
**Line**: 489

**Changed to**:
```python
factory=lambda: run_voice_direction_agent(
    context=build_voice_direction_context(
        script_qa=script_qa, 
        voice_id=req.voice_id
    )
)
```

**Why it works**:
- Uses existing `build_voice_direction_context()` helper (already imported)
- Extracts narration from script_qa into VoiceDirectionContext
- Matches the actual function signature
- Maintains Phase 1 token optimization (4,000 → 1,000 tokens)

---

## Impact

- ✅ Voice direction stage now works
- ✅ Audio generation proceeds correctly
- ✅ Token optimization maintained (75% reduction)
- ✅ No risk (uses correct architecture)

---

## Files Modified

1. `services/ai/studio/pipeline.py` - Fixed voice direction call (line 489)

---

**Status**: Ready for deployment ✅

**Note**: This was a Phase 1 migration issue where one call wasn't updated to use the new context architecture.
