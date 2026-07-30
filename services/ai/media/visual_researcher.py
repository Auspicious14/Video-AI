from __future__ import annotations

import re

from services.ai.schemas import (
    ResearchResult,
    Scene,
    VisualSearchPlan,
)


PERSON_WORDS = {
    "ceo",
    "founder",
    "president",
    "doctor",
    "scientist",
    "actor",
    "director",
    "minister",
}

LOGO_WORDS = {
    "logo",
    "brand",
    "company",
}

BUILDING_WORDS = {
    "headquarters",
    "office",
    "campus",
    "hospital",
    "factory",
}

PRODUCT_WORDS = {
    "iphone",
    "tesla",
    "vision pro",
    "chatgpt",
    "pixel",
}


def extract_entities(text: str) -> list[str]:
    """
    Very lightweight entity extraction.

    We'll replace this later with spaCy or GLiNER.
    """

    entities = []

    pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z0-9]+){0,3})"

    for match in re.findall(pattern, text):
        if len(match) > 2:
            entities.append(match.strip())

    seen = set()

    result = []

    for e in entities:
        if e.lower() not in seen:
            seen.add(e.lower())
            result.append(e)

    return result


class VisualResearcher:

    def build_plan(
        self,
        research: ResearchResult,
        scene: Scene,
    ) -> VisualSearchPlan:

        text = " ".join(
            [
                research.topic,
                scene.description,
                scene.narration,
                scene.image_prompt or "",
            ]
        )

        entities = extract_entities(text)

        alternate_queries = []

        for entity in entities:

            alternate_queries.extend(
                [
                    entity,
                    f"{entity} photo",
                    f"{entity} official",
                    f"{entity} high resolution",
                    f"{entity} press image",
                ]
            )

        lower = text.lower()

        requires_people = any(
            w in lower
            for w in PERSON_WORDS
        )

        requires_logo = any(
            w in lower
            for w in LOGO_WORDS
        )

        requires_building = any(
            w in lower
            for w in BUILDING_WORDS
        )

        requires_product = any(
            w in lower
            for w in PRODUCT_WORDS
        )

        return VisualSearchPlan(
            primary_query=scene.image_prompt
            or scene.description,
            alternate_queries=list(dict.fromkeys(alternate_queries)),
            preferred_sources=[
                "official",
                "wikimedia",
                "pexels",
                "unsplash",
            ],
            avoid_terms=[
                "illustration",
                "3d render",
                "cartoon",
                "cgi",
                "low resolution",
                "thumbnail",
            ],
            required_entities=entities,
            required_objects=[],
            visual_style="photographic",
            requires_people=requires_people,
            requires_logos=requires_logo,
            requires_buildings=requires_building,
            requires_product=requires_product,
        )