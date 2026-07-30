from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from services.ai.media.asset_types import AssetKind


class ShotType(str, Enum):
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close_up"
    MACRO = "macro"
    AERIAL = "aerial"
    SCREEN_RECORDING = "screen_recording"


class CameraMotion(str, Enum):
    STATIC = "static"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    DRONE = "drone"


class SubjectType(str, Enum):
    PERSON = "person"
    OBJECT = "object"
    LOCATION = "location"
    SCREEN = "screen"
    ABSTRACT = "abstract"
    DOCUMENT = "document"


class Emotion(str, Enum):
    CALM = "calm"
    EXCITING = "exciting"
    SERIOUS = "serious"
    HOPEFUL = "hopeful"
    SAD = "sad"
    URGENT = "urgent"


class VisualIntent(BaseModel):
    """
    Describes what we want to see,
    not where to get it.
    """

    subject: str

    subject_type: SubjectType

    action: str

    location: Optional[str] = None

    shot_type: ShotType = ShotType.MEDIUM

    motion: CameraMotion = CameraMotion.STATIC

    emotion: Emotion = Emotion.CALM

    must_show: List[str] = Field(default_factory=list)

    must_not_show: List[str] = Field(default_factory=list)

    search_keywords: List[str] = Field(default_factory=list)

    preferred_sources: List[str] = Field(default_factory=list)

    # NEW
    preferred_asset_kind: AssetKind = AssetKind.STOCK_IMAGE

    @property
    def search_query(self) -> str:
        """
        Converts the visual intent into a clean search query.
        """

        parts = [
            self.subject,
            self.action,
            self.location or "",
            *self.search_keywords,
        ]

        return " ".join(
            part.strip()
            for part in parts
            if part and part.strip()
        )
    
    @property
    def concise_search_query(self) -> str:
        """
        Generates a concise keyword-based search query suitable for Commons, Wikimedia, etc.
        Extracts key terms from subject and action, limiting to 2-6 keywords.
        
        Returns:
            A space-separated string of 2-6 keywords
        """
        import re
        
        # Common stop words to filter out
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that',
            'these', 'those', 'it', 'its', 'they', 'them', 'their'
        }
        
        # If search_keywords already provided, prefer those
        if self.search_keywords:
            # Take first 6 keywords
            return " ".join(self.search_keywords[:6])
        
        # Otherwise, extract keywords from subject and action
        text = f"{self.subject} {self.action}".lower()
        
        # Remove punctuation and split
        words = re.findall(r'\b[a-z0-9]+\b', text)
        
        # Filter stop words and short words
        keywords = [
            w for w in words 
            if w not in stop_words and len(w) > 2
        ]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        # Take 2-6 keywords
        final_keywords = unique_keywords[:6]
        
        # Ensure at least 2 keywords
        if len(final_keywords) < 2 and self.subject:
            # Fallback: use first two words of subject
            fallback = self.subject.split()[:2]
            final_keywords = [w.lower() for w in fallback if w]
        
        return " ".join(final_keywords)