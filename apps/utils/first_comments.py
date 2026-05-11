"""
First-comment composers for Facebook and LinkedIn posts.

Both platforms suppress organic reach 50-70% for posts with outbound links
in the body. The link goes in the first comment instead — but a bare URL
labelled 'Learn More:' reads like spam. These helpers craft varied,
conversational comments that:
  - reference the post content (acknowledge what was just promised)
  - call out specifics (product name, price, location)
  - rotate phrasings so a brand's feed doesn't look templated
  - end with the URL on its own line for clean preview rendering

Deterministic-per-post: we seed the template choice off the post's UUID so
the same post gets the same comment if regenerated, but different posts
rotate through the library.
"""
from __future__ import annotations

import hashlib

# ──────────────────────────────────────────────────────────────────────────
# Template libraries
# ──────────────────────────────────────────────────────────────────────────

# Templates for posts that link to a SPECIFIC PRODUCT.
# Placeholders: {product_name}, {price}, {url}
_PRODUCT_TEMPLATES_FACEBOOK = [
    "Grab yours here — {product_name} is in stock today 👇\n{url}",
    "Tap through if you want one — {price} for the {product_name}, delivery sorted:\n{url}",
    "Here's where to get it 👉 {product_name}, {price}\n{url}",
    "Skip the search — {product_name} order page:\n{url}",
    "{product_name} is back in stock. Order here before it goes again:\n{url}",
]

_PRODUCT_TEMPLATES_LINKEDIN = [
    "If you want to see the full spec for {product_name}, it's here:\n{url}",
    "More on {product_name} — including pricing and delivery — at {url}",
    "Reach out via our page if you'd like a tailored quote on {product_name}:\n{url}",
    "Specs, photos, and ordering for {product_name}:\n{url}",
    "Happy to answer questions in DMs. Product page for {product_name}:\n{url}",
]

# Templates for posts that link to a GENERAL WEBSITE / homepage.
# Placeholders: {brand}, {url}
_WEBSITE_TEMPLATES_FACEBOOK = [
    "More on what we're up to over here 👉 {url}",
    "Full story (with photos) on the site:\n{url}",
    "We share everything we're learning here — feel free to dive in:\n{url}",
    "Tap through if you want the longer version:\n{url}",
    "Bookmark us for next time 👇\n{url}",
]

_WEBSITE_TEMPLATES_LINKEDIN = [
    "If you'd like the longer write-up, it's on our site:\n{url}",
    "More context (and the rest of the story) at {url}",
    "Connect with us on the website if you'd like to talk further:\n{url}",
    "We publish the deeper thinking here — happy to discuss in comments:\n{url}",
    "Full case + numbers at {url}",
]


# ──────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────
def compose_first_comment(
    platform: str,
    post,
    product=None,
    profile=None,
) -> str:
    """
    Return a conversational first-comment string for the given platform.

    Args:
        platform: 'facebook' or 'linkedin' (others return empty string).
        post: the Post instance (used to deterministically pick a template).
        product: optional Product with .name, .product_url, .display_price.
        profile: optional UserProfile with .website_url + .company_name.

    Returns "" if there's no URL to share (nothing to comment).
    """
    if platform not in ("facebook", "linkedin"):
        return ""

    seed_id = str(getattr(post, "id", "") or "")
    bucket = _bucket_for(seed_id)

    # ── Product link branch (preferred over generic website) ──
    if product:
        product_url = (getattr(product, "product_url", "") or "").strip()
        if product_url:
            product_name = (getattr(product, "name", "") or "this product").strip()
            display_price = (getattr(product, "display_price", "") or "").strip()

            templates = (
                _PRODUCT_TEMPLATES_FACEBOOK if platform == "facebook"
                else _PRODUCT_TEMPLATES_LINKEDIN
            )
            template = templates[bucket % len(templates)]

            # Some templates use {price} — when there's no price, swap to a
            # template that doesn't, to avoid awkward blanks.
            if "{price}" in template and not display_price:
                # Pick the next template that has no {price}
                no_price_alternatives = [t for t in templates if "{price}" not in t]
                if no_price_alternatives:
                    template = no_price_alternatives[bucket % len(no_price_alternatives)]

            return template.format(
                product_name=product_name,
                price=display_price or "details inside",
                url=product_url,
            ).strip()

    # ── Generic website link branch ──
    website_url = (getattr(profile, "website_url", "") or "").strip() if profile else ""
    if website_url:
        brand = (getattr(profile, "company_name", "") or "").strip() if profile else ""
        templates = (
            _WEBSITE_TEMPLATES_FACEBOOK if platform == "facebook"
            else _WEBSITE_TEMPLATES_LINKEDIN
        )
        template = templates[bucket % len(templates)]
        return template.format(brand=brand or "us", url=website_url).strip()

    # Nothing to link — caller may decide on a no-link fallback (e.g. IG-style
    # 'save this for later' that has no URL).
    return ""


def _bucket_for(seed: str) -> int:
    """Deterministic small int from a string (stable across regenerations)."""
    if not seed:
        return 0
    h = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return int(h[:8], 16)
