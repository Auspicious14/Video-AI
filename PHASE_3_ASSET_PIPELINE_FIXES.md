# Phase 3: Real Asset Pipeline Fixes

**Date**: 2026-07-25  
**Status**: ✅ Core Issues Fixed (Tasks 1-3 complete)

## Problems Identified and Fixed

### 1. ✅ Asset Download Architecture Gap (Critical)

**Problem**: Pexels assets were discovered but never rendered. `local_path` remained empty.

**Root Cause**: The pipeline had no download step. Assets were selected in `asset_collection` but never downloaded. The `MediaDownloader.download()` method raised `NotImplementedError`.

**Fix**:
1. **Implemented `MediaDownloader.download()`** (services/ai/media/downloader.py)
   - Downloads remote assets to local disk
   - Handles caching (avoids re-downloading)
   - Retries on failure (3 attempts)
   - Validates file size (>1000 bytes)
   - Returns `LocalAsset` with populated `local_path`

2. **Added Stage 7.5: Asset Download** (services/ai/studio/pipeline.py)
   - Downloads all `selected_assets` after asset_collection
   - Populates `AssetCandidate.local_path` fields
   - Creates `downloaded_assets` list parallel to `generated_images`
   - Logs download success/failure for each asset
   - Falls back to AI generation if download fails

3. **Updated Renderer** (services/ai/studio/pipeline.py)
   - Merges `downloaded_assets` with `generated_images` before rendering
   - Accepts both `status="downloaded"` and `status="generated"`
   - **Video Priority**: Videos always beat images for same visual_index
   - **Real Asset Priority**: Downloaded assets beat AI-generated
   - Logs which asset is used for each visual

---

### 2. ✅ Unsplash & Wikimedia Provider Crashes

**Problem**: Both providers crashed with `AttributeError: 'VisualIntent' object has no attribute 'kind'`

**Root Cause**: Schema mismatch. The field is `preferred_asset_kind`, not `kind`.

**Fix**: Updated both providers:
- `services/ai/media/providers/unsplash.py`
- `services/ai/media/providers/wikimedia.py`

Changed:
```python
kind=intent.kind  # ❌ Wrong
```

To:
```python
kind=intent.preferred_asset_kind  # ✅ Correct
```

---

### 3. ✅ Poor Search Queries (Wikimedia, Unsplash, Pexels)

**Problem**: Providers received paragraph-long queries like:
```
"Founded in 1993 by Jensen Huang, Chris Malachowsky..."
```

Commons/Unsplash cannot retrieve relevant assets from paragraphs.

**Root Cause**: `VisualIntent.search_query` concatenated full `subject`, `action`, and `location` fields, which contained long descriptions.

**Fix**: Added `concise_search_query` property to VisualIntent:

**services/ai/media/visual_intent.py**:
```python
@property
def concise_search_query(self) -> str:
    """
    Generates concise keyword search (2-6 keywords).
    Filters stop words, removes duplicates.
    """
    # Implementation extracts keywords from subject/action
    # Returns: "jensen huang nvidia gpu datacenter"
```

**Updated all providers** to use `intent.concise_search_query`:
- Wikimedia
- Unsplash  
- Pexels

**Result**: 
- Bad: `"Founded in 1993 by Jensen Huang..."`
- Good: `"jensen huang nvidia headquarters"`

---

## Architectural Improvements

### Asset Flow (Before → After)

**Before** (Broken):
```
Visual Plan → Asset Collection (URLs only) → [NOTHING] → Renderer → AI generation fallback
```

**After** (Fixed):
```
Visual Plan → Asset Collection (URLs) → **Download Stage** (local_path populated) 
→ Merge with AI images → Renderer (prefers videos > images, real > AI)
```

### Renderer Asset Priority (Enforced)

```
1. Downloaded stock_video
2. Downloaded stock_image  
3. AI-generated images (fallback only)
```

Videos always beat images when both exist for same visual.

---

## Test Results

All 11 unit tests pass:
```
Ran 11 tests in 0.025s
OK
```

---

## Next Steps (Remaining Tasks)

- [ ] Task 4: Verify asset priority enforcement in production
- [ ] Task 5: Improve provider-specific matching (entity-aware searches)
- [ ] Task 6: ✅ Already done (renderer video preference implemented)
- [ ] Task 7: Add Groq 429 fallback for SEO/thumbnail/title agents
- [ ] Task 8: Improve diagnostic logging throughout asset lifecycle
- [ ] Task 9: **Full NVIDIA documentary validation**

---

## Files Modified

1. `services/ai/media/downloader.py` - Implemented download()
2. `services/ai/studio/pipeline.py` - Added download stage, merged assets, renderer priority
3. `services/ai/media/visual_intent.py` - Added concise_search_query
4. `services/ai/media/providers/pexels.py` - Use concise queries
5. `services/ai/media/providers/unsplash.py` - Use concise queries, fix schema
6. `services/ai/media/providers/wikimedia.py` - Use concise queries, fix schema

---

## Expected Documentary Quality Improvement

**Before**: 
- 0% real assets (download never happened)
- 100% AI-generated images

**After**:
- Majority real Pexels videos (GPU footage, tech centers)
- Real photos from Unsplash/Wikimedia (company headquarters, products)
- AI images ONLY where no real asset available

The final video should resemble ColdFusion/MagnatesMedia with real B-roll footage.
