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

## SCORING SCALE AUDIT

### Layer 1: Provider Results (0-1 scale)

**File**: `services/ai/media/asset.py`

```python
class MediaAsset(BaseModel):
    relevance: float = 0.80    # 0-1 scale
    quality: float = 0.80      # 0-1 scale
    freshness: float = 0.80    # 0-1 scale
    credibility: float = 0.80  # 0-1 scale
    score: float = 0.0         # Set by ranking layer
```

**Status**: ✅ Correct - All fields use 0-1 scale

### Layer 2: Ranking Layer (converts 0-1 → 0-10)

**File**: `services/ai/media/ranking.py`

```python
def score_asset(asset: MediaAsset, intent: VisualIntent) -> float:
    """Returns score between 0.0 and 1.0"""
    # ... weighted calculation ...
    
def rank_assets(...):
    score = score_asset(asset, intent)
    asset.score = round(score * 10.0, 4)  # ← Converts 0-1 to 0-10
```

**Status**: ✅ Correct - Explicitly converts to 0-10 scale

### Layer 3: Asset Collection (BROKEN - now fixed)

**File**: `services/ai/studio/asset_collection.py`

**Before (BROKEN)**:
```python
def _asset_score(candidate):
    base_score = candidate.score or 0.0              # 0-10
    video_bonus = 50.0                                # HUGE!
    credibility_score = (candidate.credibility or 0.0) * 10.0  # Already 0-1!
    quality_score = (candidate.quality or 0.0) * 10.0
    relevance_score = (candidate.relevance or 0.0) * 10.0
    return base_score + video_bonus + credibility_score + quality_score + relevance_score

# Used for BOTH ranking AND suitability_score
suitability_score=round(_asset_score(best), 2)  # Could be 100+!
```

**After (FIXED)**:
- Separated ranking score (internal, 0-100+) from suitability score (external, 0-10)
- Created two functions:
  - `_asset_ranking_score()`: Internal ranking (can exceed 100)
  - `_calculate_suitability_score()`: User-facing 0-10 score
- Added assertion to catch range violations

### Layer 4: Schema Validation (correct, caught the bug)

**File**: `services/ai/schemas.py`

```python
class AssetCandidate(BaseModel):
    suitability_score: float = Field(default=0.0, ge=0.0, le=10.0)
```

**Status**: ✅ Correct - Properly validates 0-10 range

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

### New Implementation

```python
def _asset_ranking_score(candidate):
    """Internal ranking (0-100+ scale) for sorting."""
    base_score = candidate.score or 0.0  # 0-10
    video_bonus = 50.0 if is_video else 0.0
    credibility = (candidate.credibility or 0.0) * 10.0
    quality = (candidate.quality or 0.0) * 10.0
    relevance = (candidate.relevance or 0.0) * 10.0
    return base_score + video_bonus + credibility + quality + relevance

def _calculate_suitability_score(candidate):
    """External suitability (0-10 scale) for schema."""
    base = candidate.score or 0.0  # 0-10
    credibility = (candidate.credibility or 0.0) * 10.0
    relevance = (candidate.relevance or 0.0) * 10.0
    video_adjustment = 2.0 if is_video else 0.0  # Small bonus
    
    # Weighted average + adjustment
    raw = (base * 0.4 + credibility * 0.2 + relevance * 0.4) + video_adjustment
    return min(10.0, max(0.0, raw))  # Clamp to 0-10

# Use ranking score for sorting
best = sorted(candidates, key=_asset_ranking_score, reverse=True)[0]

# Use suitability score for schema
suitability = _calculate_suitability_score(best)
assert 0.0 <= suitability <= 10.0  # Safety check
```

---

## SCALE CONSISTENCY VERIFICATION

### Provider Layer Scores (0-1 scale)
- ✅ `MediaAsset.relevance` = 0-1
- ✅ `MediaAsset.quality` = 0-1  
- ✅ `MediaAsset.freshness` = 0-1
- ✅ `MediaAsset.credibility` = 0-1

### Ranking Layer Scores (0-10 scale)
- ✅ `MediaAsset.score` = 0-10 (converted from 0-1)

### Collection Layer Scores
- ✅ Internal ranking: 0-100+ (for sorting only)
- ✅ External suitability: 0-10 (for schema)

### Schema Validation (0-10 scale)
- ✅ `AssetCandidate.suitability_score` = 0-10

---

## SAFEGUARDS ADDED

1. **Assertion** before creating AssetCandidate:
   ```python
   assert 0.0 <= suitability <= 10.0, f"suitability_score out of range: {suitability}"
   ```

2. **Explicit clamping** in `_calculate_suitability_score()`:
   ```python
   return min(10.0, max(0.0, raw_score))
   ```

3. **Clear documentation** in function docstrings explaining scale differences

4. **Separation of concerns**: Ranking score ≠ Suitability score

---

## OTHER SCORE FIELDS CHECKED

### services/ai/trends/
- `opportunity.score` - 0-100 scale (different domain)
- ✅ No conflict with asset scoring

### services/ai/schemas.py  
- `QualityIssue` - No score field
- `ScriptQAResult.score` - 0-100 scale (percentage)
- `FinalQAResult.quality_score` - 0-100 scale (percentage)
- ✅ All consistent within their domains

---

## LESSONS LEARNED

1. **Don't mix internal and external scores**: Ranking scores (for sorting) should be separate from user-facing scores (for schema)

2. **Document scale expectations**: Every score field should document its range

3. **Add assertions at boundaries**: Validate scale conversions where data crosses layers

4. **Large bonuses break scales**: A +50 bonus makes sense for ranking but destroys a 0-10 scale

5. **Schema validation caught the bug**: Pydantic's `ge=0, le=10` constraint worked as designed

---

## VERIFICATION

- [x] Root cause identified and explained
- [x] Fix implemented with proper scale separation  
- [x] Assertions added to catch future violations
- [x] Documentation added to functions
- [x] All score fields audited for consistency
- [x] Tests updated (if needed)
- [x] Pipeline tested to verify fix works
