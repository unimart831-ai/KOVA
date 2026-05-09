"""
Quality gates for generated holiday-draft content.

Every (platform, copy) emitted by the generator passes through `check_post_copy`
before a Post row is created. Failures aren't always fatal — `result.is_blocking`
distinguishes between hard rejects (e.g., banned phrase used despite explicit
prohibition) and soft warnings (e.g., suspiciously short — log it but allow).

See KOVA_HOLIDAY_AWARENESS.md section 15.5.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from apps.calendar_intel.schemas import PLATFORM_LIMITS

# Always-banned generic openers — these would make our drafts indistinguishable
# from spam. Listed regardless of holiday.
GLOBAL_BANNED_PHRASES: tuple[str, ...] = (
    "happy {holiday}",          # template leak
    "celebrate with us",
    "on this special day",
    "show your special someone",
    "thinking of you on this",
    "wishing you a",            # always followed by generic platitude
    "in today's fast-paced world",
    "elevate your",
)

# Minimum sane length per platform — if the LLM returns a 5-word post, something is wrong.
MIN_LENGTH_PER_PLATFORM = {
    "instagram": 30,
    "linkedin": 60,
    "twitter": 20,
    "facebook": 30,
}


@dataclass
class GateResult:
    """Outcome of running quality gates against one piece of copy."""
    passed: bool
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_blocking(self) -> bool:
        return bool(self.blocking_reasons)

    def add_block(self, reason: str):
        self.blocking_reasons.append(reason)
        self.passed = False

    def add_warning(self, reason: str):
        self.warnings.append(reason)


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace — used for phrase matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def check_post_copy(
    platform: str,
    text: str,
    *,
    moment_avoid_phrases: list[str] | None = None,
) -> GateResult:
    """
    Run all gates on one (platform, copy) pair.

    Returns a GateResult. Caller drops the post if `is_blocking`, otherwise
    keeps it but can log warnings.
    """
    res = GateResult(passed=True)
    text = (text or "").strip()

    # 1. Empty / too short
    if not text:
        res.add_block("empty content")
        return res

    min_len = MIN_LENGTH_PER_PLATFORM.get(platform, 20)
    if len(text) < min_len:
        res.add_warning(f"unusually short for {platform} ({len(text)} chars)")

    # 2. Over platform max length
    max_len = PLATFORM_LIMITS.get(platform, 100_000)
    if len(text) > max_len:
        res.add_block(f"exceeds {platform} max length ({len(text)} > {max_len})")

    # 3. Global banned phrases
    norm = _normalize(text)
    for phrase in GLOBAL_BANNED_PHRASES:
        if phrase in norm:
            res.add_block(f"contains banned phrase: {phrase!r}")

    # 4. Per-moment avoid phrases (case-insensitive substring match)
    for phrase in (moment_avoid_phrases or []):
        if phrase and phrase.lower() in norm:
            res.add_block(f"contains moment-specific banned phrase: {phrase!r}")

    # 5. Twitter — strict char limit (URLs count as 23 in real Twitter, but
    #    we don't try to be that smart; just enforce the raw cap with a buffer)
    if platform == "twitter" and len(text) > 280:
        res.add_block(f"twitter copy is {len(text)} chars (max 280)")

    # 6. Hashtag spam (more than 8 hashtags = noisy on every platform)
    hashtag_count = len(re.findall(r"#\w+", text))
    if hashtag_count > 8:
        res.add_warning(f"hashtag spam ({hashtag_count} hashtags)")

    # 7. URL injection — only allow URLs that look like our user's links.
    #    For now we just warn; Phase 3 will tighten this.
    if re.search(r"https?://", text):
        res.add_warning("contains a URL — verify it's the user's own link")

    return res


def filter_passing(
    candidate_posts: list[tuple[str, str]],
    moment_avoid_phrases: list[str] | None = None,
) -> tuple[list[tuple[str, str]], list[tuple[str, GateResult]]]:
    """
    Run gates on a list of (platform, text) tuples.
    Returns (passing_posts, blocked_with_reasons).
    """
    passing: list[tuple[str, str]] = []
    blocked: list[tuple[str, GateResult]] = []
    for platform, text in candidate_posts:
        result = check_post_copy(platform, text, moment_avoid_phrases=moment_avoid_phrases)
        if result.is_blocking:
            blocked.append((platform, result))
        else:
            passing.append((platform, text))
    return passing, blocked
