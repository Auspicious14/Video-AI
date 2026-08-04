from __future__ import annotations

import re

WORDS_PER_MINUTE = 145


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def estimated_duration(text: str) -> int:
    return round(word_count(text) * 60 / WORDS_PER_MINUTE)


def is_valid_length(
    text: str,
    *,
    min_words: int,
    max_words: int,
) -> bool:
    count = word_count(text)
    return min_words <= count <= max_words