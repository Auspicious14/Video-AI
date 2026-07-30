# Asset Provider Expansion Requirements

## Priority: MEDIUM (requires API integration work)

The current asset collection system has the infrastructure for tiered providers but needs additional provider implementations for Tier 1 and Tier 2 sources.

## Current Providers

Located in `services/ai/media/providers/`:
- `pexels.py` - Stock video and images
- `unsplash.py` - Stock images  
- `google_images.py` - Generic image search
- `wikimedia.py` - Wikimedia Commons
- `website.py` - Website screenshots
- `logos_dev.py` - Logo provider

## Required Tier 1 Providers (Official Sources)

### NASA Media Library
- **API**: https://api.nasa.gov/
- **Assets**: Space imagery, mission footage, press photos
- **Implementation**: Create `services/ai/media/providers/nasa.py`
- **Priority**: HIGH (excellent quality, public domain)

### ESA (European Space Agency)
- **API**: http://www.esa.int/ESA_Multimedia/
- **Assets**: Space content, Earth observation
- **Implementation**: Create `services/ai/media/providers/esa.py`

### Open Government Media
- **Sources**: 
  - USA.gov image library
  - UK Government Media
  - Australian Government Media
- **Implementation**: Create `services/ai/media/providers/government.py`

### Company Press Kits (Dynamic)
- **Strategy**: Search company websites for "/press", "/media", "/newsroom"
- **Implementation**: Enhance `website.py` with press kit detection
- **Priority**: MEDIUM

## Required Tier 2 Providers (Archives)

### Internet Archive
- **API**: https://archive.org/advancedsearch.php
- **Assets**: Historical footage, documentaries, books
- **Implementation**: Create `services/ai/media/providers/internet_archive.py`
- **Priority**: HIGH (massive historical content)

### Library of Congress
- **API**: https://www.loc.gov/apis/
- **Assets**: Historical photos, documents, recordings
- **Implementation**: Create `services/ai/media/providers/library_of_congress.py`

### Europeana
- **API**: https://pro.europeana.eu/page/apis
- **Assets**: European cultural heritage
- **Implementation**: Create `services/ai/media/providers/europeana.py`

### Flickr Creative Commons
- **API**: https://www.flickr.com/services/api/
- **Assets**: User-uploaded photos with CC licenses
- **Implementation**: Create `services/ai/media/providers/flickr_cc.py`

## Provider Implementation Template

```python
from services.ai.media.providers.base import MediaProvider
from services.ai.media.asset_types import AssetKind, AssetResult
from services.ai.media.visual_intent import VisualIntent

class NASAProvider(MediaProvider):
    name = "nasa"
    priority = 90  # High priority for official sources
    kinds = {AssetKind.STOCK_IMAGE, AssetKind.STOCK_VIDEO}
    
    async def search(
        self,
        intent: VisualIntent,
        limit: int = 10,
    ) -> list[AssetResult]:
        # 1. Build NASA API query from intent.search_keywords
        # 2. Call NASA API
        # 3. Parse results
        # 4. Return AssetResult objects with:
        #    - kind, url, title, description
        #    - score (relevance), credibility (high for NASA)
        #    - quality, licensing (public domain)
        pass
```

## Provider Registration

Update `services/ai/media/default_registry.py`:

```python
from services.ai.media.providers.nasa import NASAProvider
from services.ai.media.providers.internet_archive import InternetArchiveProvider

def build_registry():
    registry = ProviderRegistry()
    
    # Tier 1: Official sources
    registry.register(NASAProvider())
    registry.register(ESAProvider())
    registry.register(GovernmentProvider())
    
    # Tier 2: Archives
    registry.register(InternetArchiveProvider())
    registry.register(LibraryOfCongressProvider())
    registry.register(EuropeanaProvider())
    registry.register(FlickrCCProvider())
    
    # Tier 3: Stock (existing)
    registry.register(PexelsProvider())
    # ... etc
```

## Testing

For each new provider:
1. Unit test with mock API responses
2. Integration test with real API (rate-limited)
3. Verify licensing information is correct
4. Test credibility scoring boosts official sources

## Success Metrics

After implementation:
- 60-80% of assets from Tier 1-2 sources
- 10-20% from Tier 3 stock providers  
- <10% AI-generated fallbacks
