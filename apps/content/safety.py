"""
Content safety checks — lightweight moderation gate before publishing.

Flags content that may be harmful, off-brand, or AI-hallucinated before
it goes live on real social platforms. This is the last line of defense
between AI generation and the user's audience.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Keyword-based risk signals (fast, no API needed) ─────────────────────────

# Words/phrases that should NEVER appear in brand social media content.
# These fire an immediate block — content goes to PENDING_APPROVAL for human review.
BLOCKLIST_PATTERNS = [
    # Hate / discrimination
    r"\b(n[i1]gg[ae]r|f[a@]gg[o0]t|k[i1]ke|sp[i1]c|ch[i1]nk|wetback)\b",
    # Violence / threats
    r"\b(kill\s+(yourself|them|him|her)|bomb\s+threat|i\s+will\s+(shoot|murder|stab))\b",
    # Self-harm
    r"\b(commit\s+suicide|slit\s+(your|my)\s+wrists|end\s+it\s+all)\b",
    # Explicit sexual content
    r"\b(porn|xxx|sex\s+tape|nudes?\s+for\s+sale)\b",
    # Scam patterns
    r"\b(send\s+bitcoin|wire\s+transfer|nigerian\s+prince|guaranteed\s+returns)\b",
    r"\b(password|ssn|credit\s+card\s+number)\b",
]

# Patterns that indicate AI hallucination or template leakage
HALLUCINATION_PATTERNS = [
    r"\[insert\s+",           # [Insert brand name here]
    r"\{insert\s+",           # {Insert product name}
    r"\[your\s+",             # [Your Company Name]
    r"\{your\s+",             # {Your Name}
    r"\[brand\s*name\]",      # [Brand Name]
    r"\[company\s*name\]",    # [Company Name]
    r"\[product\s*name\]",    # [Product Name]
    r"as\s+an?\s+ai\b",      # "As an AI language model..."
    r"i'?m\s+an?\s+ai\b",    # "I'm an AI"
    r"language\s+model\b",    # "language model"
    r"openai|chatgpt|claude|gemini|copilot",  # AI brand leakage
]

# High engagement-bait patterns that damage brand credibility
ENGAGEMENT_BAIT_PATTERNS = [
    r"(?:like|share|retweet)\s+if\s+you\s+agree",
    r"comment\s+\d+\s+if\s+you",
]


class SafetyResult:
    """Result of a content safety check."""

    def __init__(self):
        self.is_safe = True
        self.blocked = False
        self.flags = []       # [(category, detail), ...]
        self.risk_score = 0   # 0-100

    def flag(self, category, detail, severity=10):
        self.flags.append((category, detail))
        self.risk_score = min(100, self.risk_score + severity)

    def block(self, category, detail):
        self.blocked = True
        self.is_safe = False
        self.flags.append((category, detail))
        self.risk_score = 100

    @property
    def summary(self):
        if not self.flags:
            return "Content passed all safety checks."
        return "; ".join(f"[{cat}] {det}" for cat, det in self.flags)


def check_content_safety(content_text, user=None):
    """
    Run content safety checks before publishing.

    Returns a SafetyResult with is_safe, blocked, flags, and risk_score.
    Content with risk_score >= 70 should be sent back to PENDING_APPROVAL.
    Content with blocked=True should NEVER be published.
    """
    result = SafetyResult()
    if not content_text:
        result.flag("empty", "Post has no content text", severity=30)
        return result

    text_lower = content_text.lower()

    # ── Check 1: Blocklist (immediate block) ─────────────────────────
    for pattern in BLOCKLIST_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            result.block("blocked_content", f"Matched blocked pattern: {pattern[:40]}...")
            logger.warning(
                "SAFETY BLOCK: Content flagged for blocked pattern. User=%s",
                user.email if user else "unknown",
            )
            return result  # No need to check further

    # ── Check 2: AI hallucination / template leakage ─────────────────
    for pattern in HALLUCINATION_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            result.flag(
                "ai_hallucination",
                f"AI template/hallucination detected: '{match.group()[:50]}'",
                severity=40,
            )

    # ── Check 3: Empty or too-short content ──────────────────────────
    stripped = content_text.strip()
    if len(stripped) < 10:
        result.flag("too_short", f"Content is only {len(stripped)} characters", severity=20)

    # ── Check 4: Engagement bait ─────────────────────────────────────
    for pattern in ENGAGEMENT_BAIT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            result.flag("engagement_bait", "Engagement bait detected", severity=15)
            break

    # ── Check 5: Excessive caps (shouting) ───────────────────────────
    alpha_chars = [c for c in content_text if c.isalpha()]
    if len(alpha_chars) > 20:
        caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if caps_ratio > 0.7:
            result.flag("excessive_caps", f"Content is {caps_ratio:.0%} uppercase", severity=15)

    # ── Check 6: Repetitive characters (spam-like) ───────────────────
    if re.search(r"(.)\1{9,}", content_text):
        result.flag("repetitive", "Excessive character repetition detected", severity=20)

    # ── Determine overall safety ─────────────────────────────────────
    if result.risk_score >= 70:
        result.is_safe = False

    if result.flags:
        logger.info(
            "SAFETY CHECK: score=%d safe=%s flags=%s user=%s",
            result.risk_score, result.is_safe,
            result.summary[:200], user.email if user else "unknown",
        )

    return result
