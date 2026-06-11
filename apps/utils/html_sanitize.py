"""
HTML and CSS sanitization for user-generated and LLM-generated content.

Public templates render stored HTML with ``|safe`` — every field that can
reach a browser must pass through these helpers before persistence.
"""

from __future__ import annotations

import re

import bleach
from bleach.sanitizer import Cleaner

# Tags allowed in help articles, digests, and similar rich content.
ALLOWED_TAGS = frozenset(
    {
        "p",
        "h2",
        "h3",
        "h4",
        "ul",
        "ol",
        "li",
        "strong",
        "em",
        "a",
        "blockquote",
        "code",
        "pre",
        "br",
        "hr",
    }
)

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
}

# Only http(s) and mailto links — blocks javascript: and data: URIs.
ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})

_CLEANER = Cleaner(
    tags=list(ALLOWED_TAGS),
    attributes=ALLOWED_ATTRIBUTES,
    protocols=list(ALLOWED_PROTOCOLS),
    strip=True,
    strip_comments=True,
)

# Dangerous CSS patterns on public link-in-bio pages (custom_css is injected in <style>).
_CSS_BLOCKED = re.compile(
    r"(?i)"
    r"<\s*/?\s*script"
    r"|javascript\s*:"
    r"|expression\s*\("
    r"|@import\b"
    r"|behavior\s*:"
    r"|-moz-binding\s*:"
    r"|url\s*\(\s*['\"]?\s*javascript"
)


def sanitize_html(html: str) -> str:
    """Strip XSS vectors from HTML while preserving safe formatting tags."""
    if not html:
        return ""
    return _CLEANER.clean(html)


def sanitize_user_css(css: str) -> str:
    """Strip script injection vectors from user-supplied CSS (link-in-bio Pro feature)."""
    if not css:
        return ""
    if _CSS_BLOCKED.search(css):
        css = _CSS_BLOCKED.sub("", css)
    # HTML tags have no place inside a stylesheet block.
    css = re.sub(r"<[^>]+>", "", css)
    return css.strip()
