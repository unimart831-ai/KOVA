"""Regenerate posts with low blueprint alignment scores."""

from __future__ import annotations

import logging

from apps.content.renderers import (
    apply_blueprint_renderer,
    blueprint_quality_score,
    should_retry_low_quality,
)

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 55
MAX_RETRIES = 2


def improve_low_blueprint_posts(
    post_dicts: list[dict],
    seed,
    user,
    system_prompt: str,
    platform_map: dict,
    *,
    threshold: int = DEFAULT_THRESHOLD,
) -> list[dict]:
    """
    Re-run single-platform generation for posts below blueprint quality threshold.
    Returns updated post_dicts list.
    """
    blueprint = getattr(seed, "blueprint", None) or {}
    if not blueprint or not post_dicts:
        return post_dicts

    from apps.agents.create_agent import _regenerate_single_platform
    from apps.content.models import log_gen_step

    low_platforms: list[str] = []
    for pd in post_dicts:
        scored = apply_blueprint_renderer(dict(pd), blueprint, user)
        score = blueprint_quality_score(scored, blueprint)
        plat = (pd.get("platform") or "").lower().strip()
        if should_retry_low_quality(score, threshold=threshold):
            low_platforms.append(plat)
            logger.info(
                "Blueprint retry queued: %s score=%d (seed %s)",
                plat, score, seed.id,
            )

    if not low_platforms:
        return post_dicts

    log_gen_step(
        seed,
        "polish",
        f"Improving {len(low_platforms)} post(s) to match your content blueprint.",
        ", ".join(p.title() for p in low_platforms),
    )

    updated = list(post_dicts)
    for plat in low_platforms[:MAX_RETRIES]:
        pinfo = platform_map.get(plat)
        if not pinfo:
            continue
        new_pd = _regenerate_single_platform(user, seed, pinfo, system_prompt)
        if not new_pd:
            continue
        new_pd = apply_blueprint_renderer(new_pd, blueprint, user)
        score = blueprint_quality_score(new_pd, blueprint)
        logger.info("Blueprint retry %s: new score=%d", plat, score)

        replaced = False
        for i, existing in enumerate(updated):
            if (existing.get("platform") or "").lower().strip() == plat:
                updated[i] = new_pd
                replaced = True
                break
        if not replaced:
            updated.append(new_pd)

    return updated
