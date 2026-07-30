"""
services/ai/trends/clustering.py — Topic Clustering

Responsibility:
Group raw candidate trend signals into clusters based on title Jaccard word-overlap.
This acts as initial semantic grouping before deduplication.
"""

from __future__ import annotations

import logging
import re
from typing import List, Set

from services.ai.trends.schemas import TrendCandidate

logger = logging.getLogger(__name__)


def _clean_tokenize(text: str) -> Set[str]:
    """Clean string, filter stop words, and tokenize."""
    clean = re.sub(r"[^\w\s]", "", text.lower())
    words = clean.split()
    # List of common stop words
    stop_words = {
        "a", "an", "the", "and", "or", "but", "if", "then", "of", "with",
        "for", "to", "in", "on", "at", "by", "from", "is", "are", "was",
        "were", "be", "been", "has", "have", "had", "releases", "launches",
        "announced", "about", "that", "this", "it"
    }
    return {w for w in words if w not in stop_words and len(w) > 1}


def calculate_jaccard_similarity(s1: str, s2: str) -> float:
    """Computes Jaccard word similarity between two strings."""
    tokens1 = _clean_tokenize(s1)
    tokens2 = _clean_tokenize(s2)
    
    if not tokens1 or not tokens2:
        return 0.0
        
    intersect = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    
    return float(len(intersect)) / float(len(union))


def cluster_candidates(
    candidates: List[TrendCandidate],
    threshold: float = 0.25
) -> List[List[TrendCandidate]]:
    """
    Groups raw TrendCandidate objects into clusters of similar/overlapping titles.
    Uses Single-Linkage Agglomerative Clustering approach.
    """
    if not candidates:
        return []

    clusters: List[List[TrendCandidate]] = []
    
    for candidate in candidates:
        placed = False
        
        # Check against existing clusters
        for cluster in clusters:
            # Check similarity with any element in the cluster (Single-Linkage)
            for item in cluster:
                # If titles share enough overlap, group them
                sim = calculate_jaccard_similarity(candidate.title, item.title)
                # Boost if they share exact keys like GPT-6, Claude etc.
                if sim >= threshold:
                    cluster.append(candidate)
                    placed = True
                    break
            if placed:
                break
                
        if not placed:
            # Create a new cluster
            clusters.append([candidate])

    logger.info(
        "[Clustering] Grouped %d candidates into %d clusters",
        len(candidates), len(clusters)
    )
    return clusters
