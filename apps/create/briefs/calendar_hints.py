"""Upcoming cultural / commercial moments for briefs and PLAN command."""

from __future__ import annotations

from datetime import date, timedelta


# Static anchors — extend per country as calendar_intel matures.
_KENYA_MOMENTS: list[tuple[str, str, str]] = [
    ("01-01", "national", "New Year's Day — fresh start promos"),
    ("02-14", "commercial", "Valentine's — gifts & services"),
    ("03-08", "commercial", "International Women's Day"),
    ("05-01", "national", "Labour Day — restock / staff shout-outs"),
    ("05-10", "commercial", "Mother's Day (2nd Sun May — approximate)"),
    ("06-01", "national", "Madaraka Day"),
    ("10-10", "commercial", "Moi Day / Huduma Day window"),
    ("10-20", "commercial", "Payday weekend — push offers"),
    ("12-12", "commercial", "12.12 sales season"),
    ("12-25", "commercial", "Christmas — gift guides & bundles"),
    ("12-26", "commercial", "Boxing Day clearance"),
]


def upcoming_moments(*, country: str = "KE", within_days: int = 14, today: date | None = None) -> list[dict]:
    """Return moments in the next N days for brief / PLAN copy."""
    today = today or date.today()
    country = (country or "KE").upper()
    moments: list[dict] = []

    if country in ("KE", "KENYA", ""):
        for mm_dd, category, label in _KENYA_MOMENTS:
            month, day = map(int, mm_dd.split("-"))
            try:
                event_date = date(today.year, month, day)
            except ValueError:
                continue
            if event_date < today:
                try:
                    event_date = date(today.year + 1, month, day)
                except ValueError:
                    continue
            delta = (event_date - today).days
            if 0 <= delta <= within_days:
                moments.append({
                    "date": event_date.isoformat(),
                    "days_away": delta,
                    "category": category,
                    "label": label,
                })

    # Payday weekends (last Fri/Sat of month heuristic)
    for offset in range(within_days + 1):
        d = today + timedelta(days=offset)
        if d.day >= 25 and d.weekday() in (4, 5):
            moments.append({
                "date": d.isoformat(),
                "days_away": offset,
                "category": "commercial",
                "label": "Month-end payday — strong time for promos",
            })
            break

    moments.sort(key=lambda m: m["days_away"])
    seen: set[str] = set()
    unique: list[dict] = []
    for m in moments:
        key = m["label"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)
    return unique[:5]


def format_moments_whatsapp(moments: list[dict]) -> str:
    if not moments:
        return ""
    lines = ["📅 *Coming up:*"]
    for m in moments:
        when = "today" if m["days_away"] == 0 else f"in {m['days_away']}d"
        lines.append(f"• {m['label']} ({when})")
    return "\n".join(lines)
