"""Lightweight sentiment classification for review responses.

A keyword-and-emoji heuristic. Fast, free, no LLM round-trip.
"""
from __future__ import annotations

import re


_POSITIVE_TOKENS = {
    # English
    "great", "good", "awesome", "amazing", "love", "loved", "perfect", "best",
    "excellent", "wonderful", "fantastic", "happy", "recommend", "thanks",
    "thank you", "asante", "smooth", "professional", "friendly", "quick",
    # Swahili
    "poa", "sawa", "vizuri", "nzuri", "nimefurahia", "asante sana",
}

_NEGATIVE_TOKENS = {
    "bad", "terrible", "awful", "worst", "horrible", "rude", "slow",
    "disappointed", "never", "not recommend", "waste", "late", "broken",
    "hate", "ugly", "unprofessional", "complain", "refund",
    # Swahili
    "mbaya", "hapana", "hapendi", "sijaridhika",
}

_POSITIVE_EMOJI = {"❤", "\U0001F60D", "\U0001F44D", "\U0001F525", "\U0001F44C", "\U0001F970", "✨"}
_NEGATIVE_EMOJI = {"\U0001F44E", "\U0001F620", "\U0001F621", "\U0001F92C", "\U0001F61E"}


def classify(text: str) -> tuple[str, float]:
    """Return (label, score) where label in {positive, neutral, negative}
    and score ∈ [0, 1]: 0=most negative, 1=most positive."""
    if not text:
        return "neutral", 0.5

    lower = text.lower()
    pos_hits = sum(1 for t in _POSITIVE_TOKENS if t in lower)
    neg_hits = sum(1 for t in _NEGATIVE_TOKENS if t in lower)
    pos_hits += sum(1 for e in _POSITIVE_EMOJI if e in text)
    neg_hits += sum(1 for e in _NEGATIVE_EMOJI if e in text)

    # 5-star strings like "5/5" or "★★★★★"
    if re.search(r"\b5\s*/\s*5\b", text) or text.count("★") >= 4:
        pos_hits += 2
    if re.search(r"\b[12]\s*/\s*5\b", text) or text.count("☆") >= 4:
        neg_hits += 2

    if pos_hits == 0 and neg_hits == 0:
        # Look at length / exclamation as a weak signal
        if "!" in text and len(text) < 60:
            return "positive", 0.65
        return "neutral", 0.5

    total = pos_hits + neg_hits
    score = pos_hits / total

    if score >= 0.7:
        return "positive", score
    if score <= 0.3:
        return "negative", score
    return "neutral", score
