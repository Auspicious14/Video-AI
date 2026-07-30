# Production Hotfix: Visual Planner NoneType Error

**Date**: 2026-07-26 22:26  
**Severity**: HIGH (production blocker)  
**Status**: ✅ FIXED

---

## Error Report

**Error**:
```python
AttributeError: 'NoneType' object has no attribute 'visual_style'
```

**Stack Trace**:
```
File "/Users/Products/videoAI/services/ai/studio/visual_planner.py", line 237
    merged.append(_fallback_prompt_item(item, visual_plan.visual_style))
                                              ^^^^^^^^^^^^^^^^^^^^^^^^
```

**Context**: YouTube studio pipeline failed during image generation planning stage

---

## Root Cause

**File**: `services/ai/studio/visual_planner.py`  
**Line**: 237

**Problem**: Code referenced `visual_plan.visual_style` but `visual_plan` was None in this context.

**Why It Happened**:
1. Function `run_image_generation_planner_agent()` accepts two params: `context` and `visual_plan`
2. When `context` is provided (new Phase 1 architecture), `visual_plan` is None
3. Line 237 incorrectly used `visual_plan.visual_style` instead of `context.style_reference`
4. This caused AttributeError when visual_plan was None

**Code Analysis**:
```python
# Line 189-194: visual_plan is optional, context is built from it if provided
if context is None:
    if visual_plan is None:
        raise ValueError("context or visual_plan is required")
    context = ImageGenerationContext(
        style_reference=visual_plan.visual_style,  # ← builds context from visual_plan
        required_visuals=[...],
    )

# Line 237: Bug - references visual_plan which may be None
merged.append(_fallback_prompt_item(item, visual_plan.visual_style))
                                          ^^^^^^^^^^^^^ BUG: can be None!
```

---

## Fix Applied

**File**: `services/ai/studio/visual_planner.py`  
**Line**: 237

**Before**:
```python
merged.append(_fallback_prompt_item(item, visual_plan.visual_style))
```

**After**:
```python
# Use context.style_reference, not visual_plan.visual_style (visual_plan may be None)
merged.append(_fallback_prompt_item(item, context.style_reference))
```

**Rationale**: 
- `context` is guaranteed to exist (validated at line 189)
- `context.style_reference` always contains the style (either from passed context or built from visual_plan)
- No risk of NoneType error

---

## Testing

**Manual Test**: Production pipeline that was failing should now succeed

**Verification**:
1. Visual planning stage creates context
2. Image generation planning receives context
3. Fallback uses `context.style_reference` safely
4. No NoneType errors

---

## Impact

**Affected**: All YouTube studio video generation  
**Fixed**: Immediately (single line change)  
**Risk**: None (uses correct variable that's guaranteed to exist)

---

## Prevention

**Why Wasn't This Caught Earlier?**:
- Phase 1 refactor introduced new context architecture
- Old code path using `visual_plan` param was preserved for backwards compat
- New code path always passes `context`, making `visual_plan` None
- Line 237 was never updated to use new architecture

**How to Prevent**:
1. Add test that exercises fallback path with context=provided, visual_plan=None
2. Code review checklist: verify all param references match function signature logic
3. Add type hints that make optional params explicit

---

## Related Issues

This is similar to the NoneType comparison bugs fixed earlier in `services/ai/client.py`. Both involved assumptions about optional parameters without proper None guards.

---

**Status**: ✅ FIXED  
**Deployed**: Ready for immediate deployment  
**Testing**: Manual verification recommended
