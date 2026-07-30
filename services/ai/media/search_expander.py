"""
Expand one visual intent into many high-quality search queries.

This module is deterministic (no LLM required).
"""

from __future__ import annotations

from typing import List

from services.ai.schemas import VisualSearchPlan


QUALITY_SUFFIXES = [

    "official",

    "press",

    "high resolution",

    "photo",

    "editorial",

    "news",

]

EVENT_SUFFIXES = [

    "announcement",

    "launch",

    "keynote",

    "conference",

]

PERSON_SUFFIXES = [

    "portrait",

    "speaking",

    "on stage",

]

BUILDING_SUFFIXES = [

    "exterior",

    "headquarters",

    "campus",

]

PRODUCT_SUFFIXES = [

    "close up",

    "front view",

    "product photo",

]


class SearchExpander:

    def expand(
        self,
        plan: VisualSearchPlan,
    ) -> List[str]:

        queries = []

        primary = plan.primary_query.strip()

        queries.append(primary)

        queries.extend(plan.alternate_queries)

        for entity in plan.required_entities:

            queries.append(entity)

            for suffix in QUALITY_SUFFIXES:
                queries.append(f"{entity} {suffix}")

            if plan.requires_people:

                for suffix in PERSON_SUFFIXES:
                    queries.append(f"{entity} {suffix}")

            if plan.requires_buildings:

                for suffix in BUILDING_SUFFIXES:
                    queries.append(f"{entity} {suffix}")

            if plan.requires_product:

                for suffix in PRODUCT_SUFFIXES:
                    queries.append(f"{entity} {suffix}")

        for suffix in EVENT_SUFFIXES:

            queries.append(f"{primary} {suffix}")

        cleaned = []

        seen = set()

        for q in queries:

            q = " ".join(q.split())

            key = q.lower()

            if key not in seen:

                seen.add(key)

                cleaned.append(q)

        return cleaned