# Asset Scoring Scale Audit and Fix

**Date**: 2026-07-25  
**Issue**: ValidationError - suitability_score=76.5 exceeds schema limit of 10.0  
**Status**: ✅ FIXED

---

## ROOT CAUSE ANALYSIS

### The Bug

Phase 2 improvements added video prioritization in `asset_collection.py` with a `_asset_score()` function that:

1. Used `base_score` (0-10 scale from ranking layer)
2. Added `video_bonus = 50.0` for videos
3. Multiplied credibility, quality, relevance by 10 (treating them as 0-1 when they're already weighted)
4. Summed these to get ranking score (could exceed 100)
5. **Used this ranking score directly as `suitability_score`** (expects 0-10)

### Example Calculation

```
base_score = 8.0          # from ranking layer (0-10)
video_bonus = 50.0        # HUGE bonus
credibility * 10 = 8.0    # 0.8 * 10
quality * 10 = 8.0        # 0.8 * 10
relevance * 10 = 8.0      # 0.8 * 10
───────────────────────
Total = 82.0              # Way over 10!
```

This 82.0 was passed to `AssetCandidate.suitability_score` which expects 0-10.

---

## THE FIX

### Separated Concerns

**Internal Ranking Score** (0-100+ scale):
- Used ONLY for sorting candidates
- Can have large bonuses (video_bonus = 50.0)
- Purpose: Pick the best asset from candidates

**External Suitability Score** (0-10 scale):
- Used for AssetCandidate schema
- Normalized weighted average
- Purpose: Show user how good the asset is

### Implementation

Two separate functions now handle these different concerns:

1. `_asset_ranking_score()`: Internal ranking (0-100+) for sorting
2. `_calculate_suitability_score()`: External score (0-10) for schema

### Safeguards Added

1. Assertion before creating AssetCandidate validates 0-10 range
2. Explicit clamping in calculation: `min(10.0, max(0.0, raw_score))`
3. Clear documentation in function docstrings
