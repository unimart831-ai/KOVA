"""
Seed loader — populates the Holiday table from:
  1. Curated YAML (apps/calendar_intel/seeds/curated_moments.yaml)
  2. python-holidays library (statutory holidays per country)

Idempotent: run repeatedly. Updates by slug.

See KOVA_HOLIDAY_AWARENESS.md §9 for design.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from django.db import transaction
from django.utils.text import slugify

from apps.calendar_intel.models import Holiday

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).resolve().parent / "seeds"
CURATED_YAML = SEEDS_DIR / "curated_moments.yaml"
COUNTRY_RELIGIONS_YAML = SEEDS_DIR / "country_religion_defaults.yaml"

# Countries we seed from python-holidays in Phase 1. Add more as we expand markets.
PYTHON_HOLIDAYS_COUNTRIES = ["RW", "KE", "TZ", "UG", "US", "GB"]


# ──────────────────────────────────────────────────────────────────────────
# YAML curated loader
# ──────────────────────────────────────────────────────────────────────────
def load_curated() -> int:
    """Load curated_moments.yaml into Holiday table. Returns count upserted."""
    if not CURATED_YAML.exists():
        logger.warning("Curated YAML not found at %s", CURATED_YAML)
        return 0

    with CURATED_YAML.open("r", encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []

    count = 0
    with transaction.atomic():
        for entry in entries:
            count += _upsert_curated_entry(entry)
    return count


def _upsert_curated_entry(entry: dict[str, Any]) -> int:
    slug = entry.get("slug")
    if not slug:
        logger.warning("Skipping entry without slug: %s", entry.get("name"))
        return 0

    defaults = {
        "name": entry["name"],
        "short_description": entry.get("short_description", ""),
        "date_type": entry["date_type"],
        "date_config": entry.get("date_config", {}),
        "countries": entry.get("countries", []),
        "excluded_countries": entry.get("excluded_countries", []),
        "category": entry["category"],
        "religion": entry.get("religion", "") or "",
        "industries": entry.get("industries", []),
        "sensitivity_level": entry.get("sensitivity_level", "safe"),
        "requires_opt_in": entry.get("requires_opt_in", False),
        "default_relevance_score": entry.get("default_relevance_score", 50),
        "suggested_post_count": entry.get("suggested_post_count", 2),
        "lead_time_days": entry.get("lead_time_days", 7),
        "tone_hint": entry.get("tone_hint", "") or "",
        "angles": entry.get("angles", []),
        "avoid_phrases": entry.get("avoid_phrases", []),
        "is_active": entry.get("is_active", True),
        "source": "curated",
        "notes": entry.get("notes", ""),
    }

    obj, created = Holiday.objects.update_or_create(slug=slug, defaults=defaults)
    logger.debug("%s curated holiday: %s", "Created" if created else "Updated", obj.name)
    return 1


# ──────────────────────────────────────────────────────────────────────────
# python-holidays integration
# ──────────────────────────────────────────────────────────────────────────
def load_from_python_holidays(years: list[int] | None = None) -> int:
    """
    Pull statutory holidays from the `holidays` library for our supported
    countries and create Holiday rows for any not already covered by
    curated YAML.

    The library returns date → name pairs for a given year. We extract a
    canonical (name, month, day) triple per country and upsert as 'fixed'
    Holiday rows. Holidays with non-fixed dates (Easter-tied, lunar) are
    skipped — those should live in curated YAML for clarity.
    """
    try:
        import holidays as ph_lib
    except ImportError:
        logger.warning("python-holidays not installed; skipping library import")
        return 0

    from datetime import date

    years = years or _default_years()
    count = 0

    with transaction.atomic():
        for country in PYTHON_HOLIDAYS_COUNTRIES:
            try:
                country_holidays = ph_lib.country_holidays(country, years=years)
            except Exception as exc:
                logger.warning("Failed to load holidays for %s: %s", country, exc)
                continue

            # Group by canonical (month, day, name) — only keep fixed dates that
            # repeat year-over-year.
            seen: dict[tuple[int, int], dict] = {}
            for d, name in country_holidays.items():
                key = (d.month, d.day)
                if key not in seen:
                    seen[key] = {"name": name, "dates": [d]}
                else:
                    seen[key]["dates"].append(d)
                    # Use shortest name as canonical (avoids "X (observed)")
                    if len(name) < len(seen[key]["name"]):
                        seen[key]["name"] = name

            for (month, day), info in seen.items():
                # Only seed if it appears across ≥ ceil(half) of our years —
                # filters out one-time observances.
                if len(info["dates"]) < max(1, len(years) // 2):
                    continue

                clean_name = _clean_holiday_name(info["name"])
                slug = slugify(f"{country}-{clean_name}")[:120]

                # Don't override curated entries
                if Holiday.objects.filter(slug=slug, source="curated").exists():
                    continue

                obj, created = Holiday.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "name": f"{clean_name} ({country})",
                        "short_description": f"National observance in {country}.",
                        "date_type": "fixed",
                        "date_config": {"month": month, "day": day},
                        "countries": [country],
                        "category": "national_holiday",
                        "sensitivity_level": "safe",
                        "default_relevance_score": 60,
                        "suggested_post_count": 1,
                        "lead_time_days": 4,
                        "tone_hint": "respectful",
                        "source": "python-holidays",
                        "is_active": True,
                    },
                )
                if created:
                    count += 1

    return count


def _clean_holiday_name(name: str) -> str:
    """Strip parenthetical observance markers and trailing whitespace."""
    cleaned = name
    for marker in ["(observed)", "(Observed)", "(estimated)", "(Estimated)"]:
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip()


def _default_years() -> list[int]:
    """Get current + next 2 years for occurrence stability."""
    from django.utils import timezone
    current = timezone.now().year
    return [current, current + 1, current + 2]


# ──────────────────────────────────────────────────────────────────────────
# Country → religion defaults
# ──────────────────────────────────────────────────────────────────────────
def country_religion_defaults() -> dict[str, list[str]]:
    """Read country_religion_defaults.yaml. Returns {country_code: [religion, ...]}."""
    if not COUNTRY_RELIGIONS_YAML.exists():
        return {}
    with COUNTRY_RELIGIONS_YAML.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ──────────────────────────────────────────────────────────────────────────
# Top-level API
# ──────────────────────────────────────────────────────────────────────────
def seed_all() -> dict[str, int]:
    """Run full seed cycle. Returns counts."""
    curated = load_curated()
    library = load_from_python_holidays()
    return {"curated": curated, "library": library}
