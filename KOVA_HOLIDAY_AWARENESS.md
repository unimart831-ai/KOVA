# Kova Holiday & Cultural Moments Awareness — A to Z Specification

**Status:** Planning / Pre-build
**Owner:** Iranzi Innocent (Founder), Claude (Technical Co-founder)
**Last Updated:** 2026-05-09
**Target ship:** Phase 1 — 2 weeks from build start; Phase 2 — +2 weeks; Phase 3 — +1 week

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Strategic Positioning](#2-strategic-positioning)
3. [Vision & Product Principles](#3-vision--product-principles)
4. [User Stories](#4-user-stories)
5. [System Architecture](#5-system-architecture)
6. [The Three Layers of Moments](#6-the-three-layers-of-moments)
7. [Data Models](#7-data-models)
8. [Date Calculation Engine](#8-date-calculation-engine)
9. [Holiday Data Sources & Seeding](#9-holiday-data-sources--seeding)
10. [Country, Market, and Locale Handling](#10-country-market-and-locale-handling)
11. [Industry-Specific Moments](#11-industry-specific-moments)
12. [Sensitivity & Opt-In Framework](#12-sensitivity--opt-in-framework)
13. [Relevance Scoring Algorithm](#13-relevance-scoring-algorithm)
14. [The Holiday Watcher Agent](#14-the-holiday-watcher-agent)
15. [Content Generation Pipeline](#15-content-generation-pipeline)
16. [Custom Events](#16-custom-events)
17. [Integration with Daily Brief](#17-integration-with-daily-brief)
18. [Integration with Content Studio](#18-integration-with-content-studio)
19. [Integration with Calendar App](#19-integration-with-calendar-app)
20. [Integration with Website Generator](#20-integration-with-website-generator)
21. [Onboarding Flow](#21-onboarding-flow)
22. [User Preference UI](#22-user-preference-ui)
23. [Notifications](#23-notifications)
24. [URL Routes & API Endpoints](#24-url-routes--api-endpoints)
25. [Django Application Structure](#25-django-application-structure)
26. [Failure Modes & Mitigations](#26-failure-modes--mitigations)
27. [Pricing & Plan Tiers](#27-pricing--plan-tiers)
28. [Implementation Roadmap](#28-implementation-roadmap)
29. [Open Questions](#29-open-questions)
30. [Glossary](#30-glossary)

---

## 1. Executive Summary

The Holiday & Cultural Moments Awareness system gives Kova **cultural fluency**: the ability to anticipate holidays, religious observances, commercial moments, and culturally significant days that matter to a user's business — and to draft content for them in advance.

When Mother's Day is 9 days away, Kova has already drafted three posts in the user's voice, tied to their actual products, sensitive to their market context. When Eid arrives in a Muslim-majority market, Kova respects the moment without forcing it into a non-relevant business. When a Rwandan business approaches Liberation Day, Kova knows what that means locally — something Hootsuite and Buffer get wrong.

This is not a holiday calendar feature. It is a **proactive content-anticipation engine** powered by a structured knowledge base of moments, an opt-in preference system that respects sensitivity, and an agent loop that drafts content with lead time.

The competitive advantage: **no global tool nails East African holidays**, and no tool combines holiday awareness with brand voice and product context. Kova does both.

---

## 2. Strategic Positioning

### What we are competing against

| Tool | Holiday handling | Gap we exploit |
|---|---|---|
| Hootsuite, Buffer | Hardcoded US/UK calendar with manual overrides | No East Africa, no industry intelligence, no auto-drafts |
| Later, Sprout Social | Editorial calendar with holiday markers | Static markers — no content generation |
| Custom Google Calendar | User maintains own list | All manual; no draft generation |
| ChatGPT prompts | User asks ChatGPT for holiday post ideas | Generic; no brand voice, no auto-scheduling |

### Where we win

1. **East African market expertise.** Liberation Day, Heroes Day, Saba Saba, Mashujaa Day, Eid celebrations local to the region — surfaced and tone-appropriate.
2. **Industry-aware suggestions.** A florist gets Valentine's hard. A B2B SaaS gets it ignored.
3. **Brand voice fidelity.** Holiday content goes through the same voice pipeline as everything else — never generic.
4. **Lead time as a feature.** 7 days ahead in the Daily Brief. Drafts already waiting.
5. **Sensitivity by default.** Religious and political days are opt-in. Awareness days suggested but never auto-drafted.

### Category framing

We're not building a "holiday calendar." We're building **"the AI that knows what month it is in your customer's life."** That framing matters for marketing and for product decisions.

---

## 3. Vision & Product Principles

### North star

> *Every Kova user wakes up to drafted, voice-perfect content for the moments their customers will care about — without having to remember a single date themselves.*

### Product principles

1. **Anticipation over reaction.** 7-day lead time minimum for major holidays. We never let a user be caught flat-footed.
2. **Drafts, not auto-posts.** Holiday content is high-stakes. We always require user approval. No exceptions in Phase 1.
3. **Sensitivity by default.** Religious/political/contested holidays are off until the user opts in.
4. **Brand voice always.** No generic templates. Every post passes through brand voice generation.
5. **Local context first.** Country, city, and market shape the suggestions. A US user does not get Saba Saba; a Rwandan user does not get Thanksgiving (unless they ask).
6. **Restraint over volume.** Suggest top 3 monthly relevant moments per user, not 30. Holiday fatigue is real.
7. **Personal over prescribed.** Custom events (anniversaries, launches) are first-class — not a separate feature.
8. **Industry-aware.** Same engine, different relevance per industry.
9. **Transparent reasoning.** When we suggest a holiday, the user sees why ("Relevant for retail in Kigali, suggested 2 posts").
10. **Easy to mute.** One click to dismiss a holiday for this year, one click to mute permanently.

### What we explicitly do not build

- ❌ Auto-publish without approval
- ❌ Generic holiday templates ("Happy Mother's Day to all moms!")
- ❌ Religion-collection forms (we infer lightly from country)
- ❌ Political stance suggestions (Pride / Remembrance Day / Independence Day in disputed regions are opt-in only)
- ❌ Holiday post for every minor awareness day (#NationalDoughnutDay flooding the brief)

---

## 4. User Stories

### Discovery & onboarding

- **US-1:** As a new user, during onboarding I want to confirm which markets I serve so Kova surfaces only relevant holidays.
- **US-2:** As a new user, I want to see which holiday categories Kova will track for me, with the option to opt out of religious/political ones.
- **US-3:** As a new user, I want to add my own custom moments (business anniversary, product launch dates) right in onboarding.

### Daily Brief integration

- **US-4:** As a user reading my Daily Brief, I want to see a preview of upcoming holidays/moments in the next 14 days so I can plan ahead.
- **US-5:** As a user, when a holiday is 7 days away, I want to see drafted posts for it in my brief so I can approve quickly.
- **US-6:** As a user, I want each suggested holiday to show why it's relevant to me ("Mother's Day matches your industry: gifts").

### Content drafting

- **US-7:** As a user, I want holiday post drafts to use my brand voice and reference my products specifically — not generic copy.
- **US-8:** As a user, I want each holiday to come with 2–3 different angles so I can pick what fits.
- **US-9:** As a user, I want to one-click approve a holiday draft and have Kova schedule it at the optimal time on the day.

### Preference management

- **US-10:** As a user, I want to mute a holiday I don't celebrate without affecting other users.
- **US-11:** As a user, I want to add custom recurring events that matter to me.
- **US-12:** As a user, I want to change which markets I serve (e.g., add Uganda) and have my holiday list update.

### Sensitivity

- **US-13:** As a user in a multi-religious market, I want both Christmas and Eid surfaced as opt-in so I can choose without being prompted in a one-sided way.
- **US-14:** As a user, I want to never receive suggestions for holidays my faith doesn't observe — but only if I told you that explicitly.
- **US-15:** As a user in a contested political region, I want politically charged holidays to require my explicit confirmation.

### Calendar & website

- **US-16:** As a user looking at my content calendar, I want holiday markers visible so I can see at a glance what's coming.
- **US-17:** As a user with a Kova website, I want my hero CTA to update for major shopping holidays automatically (e.g., "Order before Mother's Day").

### Trust & restraint

- **US-18:** As a user, I never want Kova to auto-publish a holiday post without my explicit approval.
- **US-19:** As a user, I want a clear way to dismiss a holiday for this year only.
- **US-20:** As a user, I want to see how my holiday posts performed so I can decide whether to do more next year.

---

## 5. System Architecture

### High-level data flow

```
┌─────────────────────────────────────────────────────────────────┐
│                  GLOBAL HOLIDAY KNOWLEDGE BASE                   │
│                                                                   │
│   python-holidays library  +  curated DB  +  Hijri converter    │
│   (statutory & national)      (commercial    (lunar dates)       │
│                                & cultural)                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              HOLIDAY MODEL (apps/calendar_intel)                 │
│              Holiday + UserHolidayPreference                     │
│              + CustomEvent + HolidayDraft                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│             HOLIDAY WATCHER AGENT (Celery beat — nightly)        │
│                                                                   │
│  For each user:                                                   │
│  1. Compute upcoming moments next 30 days for user's markets    │
│  2. Filter by user preferences + opt-ins                        │
│  3. Score relevance (industry × moment × user signals)          │
│  4. Top 3 enter "active draft window" (7-day lead)              │
│  5. Generate post drafts in user's voice via Claude             │
│  6. Queue drafts in Content Studio                              │
│  7. Push to next Daily Brief                                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SURFACES                                   │
│  ┌─────────────┬─────────────┬──────────────┬─────────────┐    │
│  │ Daily Brief │ Content     │ Calendar     │ Website CTA │    │
│  │ calendar    │ Studio      │ moment       │ banner      │    │
│  │ widget +    │ "Holiday    │ markers      │ updates     │    │
│  │ drafts      │ drafts (3)" │              │ (Phase 2)   │    │
│  └─────────────┴─────────────┴──────────────┴─────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Component responsibilities

| Component | Responsibility |
|---|---|
| **Holiday seed module** | Loads/refreshes the knowledge base from library + curated data |
| **Date engine** | Computes occurrences (fixed, nth-weekday, Easter, Hijri) for any year |
| **Relevance scorer** | Per-user × per-moment relevance score (0–100) |
| **Watcher agent** | Nightly Celery task; orchestrates draft generation |
| **Content generator** | Calls Claude with brand voice + holiday context |
| **Preference engine** | Resolves opt-in/opt-out per user |
| **Surfaces (Brief, Studio, Calendar)** | Read-only consumers of the data |

---

## 6. The Three Layers of Moments

### Layer 1: Global & Statutory Holidays

**Examples:** Christmas, New Year, Easter, Eid al-Fitr, Mother's Day, Father's Day, Independence Day, Liberation Day, Heroes Day, Diwali, Chinese New Year.

**Source:** `python-holidays` library + Hijri calendar package + curated supplements.

**Filtered by:** User's country + secondary markets.

**Default behavior:** Most are opt-out (statutory holidays); religious holidays are opt-in.

### Layer 2: Commercial & Cultural Moments

**Examples:** Black Friday, Cyber Monday, Earth Day, World Coffee Day, Singles' Day, Small Business Saturday, Valentine's Day, Halloween (where culturally relevant).

**Source:** Curated DB seeded by us, expandable by editorial team or via admin.

**Filtered by:** User's industry + opted-in tags.

**Default behavior:** Industry-relevant ones are opt-out; awareness days are surfaced but not auto-drafted.

### Layer 3: Personal & Business Events

**Examples:** Business anniversary, product launch dates, founder's birthday (if user wants), team milestones, "1 year since first 100 customers."

**Source:** User-entered.

**Filtered by:** User-controlled — visible to user only.

**Default behavior:** Always-on for the user who created them; never shared across users.

---

## 7. Data Models

### 7.1 Holiday

```python
class Holiday(models.Model):
    """
    Master record for a recognized holiday or cultural moment.
    One row per unique holiday (not per occurrence).
    Occurrences are computed by the date engine.
    """
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True)
    short_description = models.CharField(max_length=500)

    # Date logic
    DATE_TYPES = [
        ("fixed", "Fixed (same date every year)"),
        ("nth_weekday", "Nth weekday of a month"),
        ("computed_easter", "Computed from Easter"),
        ("lunar_islamic", "Hijri lunar calendar"),
        ("lunar_chinese", "Chinese lunar calendar"),
        ("custom_function", "Custom date function"),
    ]
    date_type = models.CharField(max_length=20, choices=DATE_TYPES)
    date_config = models.JSONField()
    # Examples:
    #   fixed: {"month": 12, "day": 25}
    #   nth_weekday: {"month": 5, "weekday": 6, "n": 2}  (2nd Sunday May = Mother's Day)
    #   computed_easter: {"offset_days": -2}  (Good Friday)
    #   lunar_islamic: {"hijri_month": 10, "hijri_day": 1}  (Eid al-Fitr)
    #   custom_function: {"function_name": "third_friday_after_thanksgiving"}

    # Geographic scope
    countries = models.JSONField(default=list)
    # ISO-3166-1 alpha-2 codes; ["RW", "KE", "TZ", "UG"] for East Africa,
    # [] for global (e.g., World Coffee Day)
    excluded_countries = models.JSONField(default=list)
    # For nuanced cases: a global holiday with regional exclusions

    # Categorization
    CATEGORIES = [
        ("national_holiday", "National / statutory holiday"),
        ("religious", "Religious observance"),
        ("commercial", "Commercial / shopping holiday"),
        ("cultural", "Cultural moment"),
        ("awareness_day", "Awareness day"),
        ("industry_specific", "Industry-specific moment"),
        ("personal", "Personal / business event"),
    ]
    category = models.CharField(max_length=30, choices=CATEGORIES)

    religion = models.CharField(
        max_length=30,
        blank=True,
        choices=[
            ("christian", "Christian"),
            ("muslim", "Muslim"),
            ("hindu", "Hindu"),
            ("buddhist", "Buddhist"),
            ("jewish", "Jewish"),
            ("secular", "Secular"),
            ("", "None / not applicable"),
        ],
    )
    industries = models.JSONField(default=list)
    # ["retail", "f_and_b", "services", "b2b", "creative", "health"], or [] for all

    # Sensitivity
    SENSITIVITY = [
        ("safe", "Safe — broad audience, low risk"),
        ("consider", "Consider — depends on market context"),
        ("high", "High — politically/religiously charged, requires opt-in"),
    ]
    sensitivity_level = models.CharField(max_length=20, choices=SENSITIVITY, default="safe")
    requires_opt_in = models.BooleanField(default=False)

    # Defaults for the relevance scorer
    default_relevance_score = models.IntegerField(default=50)  # 0–100
    suggested_post_count = models.IntegerField(default=2)
    lead_time_days = models.IntegerField(default=7)

    # Content guidance
    tone_hint = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("warm", "Warm / heartfelt"),
            ("celebratory", "Celebratory / festive"),
            ("respectful", "Respectful / reverent"),
            ("playful", "Playful / fun"),
            ("urgent", "Urgent / commercial"),
            ("informative", "Informative / educational"),
        ],
    )
    angles = models.JSONField(default=list)
    # ["Honor the moms in your community",
    #  "A discount for Mom this year",
    #  "Behind-the-scenes from our female founders"]

    avoid_phrases = models.JSONField(default=list)
    # ["Happy {holiday}", "Celebrate with us", "On this special day"]
    # Used as a "do not generate" guardrail in the prompt

    # Admin / metadata
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=100, blank=True)  # "python-holidays", "curated", etc.
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["religion"]),
        ]
```

### 7.2 HolidayOccurrence

```python
class HolidayOccurrence(models.Model):
    """
    Pre-computed occurrence of a holiday for a specific year.
    Populated annually for the next 2 years to make queries cheap.
    """
    holiday = models.ForeignKey(Holiday, on_delete=models.CASCADE, related_name="occurrences")
    year = models.PositiveIntegerField()
    date = models.DateField()
    notes = models.CharField(max_length=200, blank=True)
    # e.g., "Eid al-Fitr 2026 — start date approximate, lunar"

    class Meta:
        unique_together = [("holiday", "year")]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["year", "date"]),
        ]
```

### 7.3 UserHolidayPreference

```python
class UserHolidayPreference(models.Model):
    """
    Per-user override for a specific holiday.
    Absence of a row means: use Holiday defaults (filtered by user.country/industry).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="holiday_preferences",
    )
    holiday = models.ForeignKey(Holiday, on_delete=models.CASCADE)

    is_enabled = models.BooleanField(default=True)
    custom_relevance_score = models.IntegerField(null=True, blank=True)
    custom_lead_time_days = models.IntegerField(null=True, blank=True)
    custom_post_count = models.IntegerField(null=True, blank=True)
    auto_draft_posts = models.BooleanField(default=True)

    # Mute behaviors
    muted_until = models.DateField(null=True, blank=True)
    # User can mute "this year only" by setting muted_until=Jan 1 next year

    notes = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "holiday")]
```

### 7.4 CustomEvent

```python
class CustomEvent(models.Model):
    """
    User-defined personal or business moments.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custom_events",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    date = models.DateField()
    RECURRENCE = [
        ("once", "One-time"),
        ("yearly", "Annually on this date"),
        ("monthly", "Monthly"),
    ]
    recurrence = models.CharField(max_length=20, choices=RECURRENCE, default="yearly")

    # Tone & content
    tone_hint = models.CharField(max_length=50, blank=True)
    angles = models.JSONField(default=list)
    suggested_post_count = models.IntegerField(default=1)
    lead_time_days = models.IntegerField(default=3)

    is_active = models.BooleanField(default=True)
    auto_draft_posts = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date"]
```

### 7.5 HolidayDraft

```python
class HolidayDraft(models.Model):
    """
    Tracks each holiday/event draft cycle to prevent duplicate generation
    and to provide audit/debug visibility.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="holiday_drafts",
    )

    # The moment — exactly one of these is set
    holiday_occurrence = models.ForeignKey(
        HolidayOccurrence, null=True, blank=True, on_delete=models.SET_NULL,
    )
    custom_event = models.ForeignKey(
        CustomEvent, null=True, blank=True, on_delete=models.SET_NULL,
    )

    target_date = models.DateField()
    relevance_score = models.IntegerField()

    STATUS = [
        ("queued", "Queued for generation"),
        ("generating", "Generating"),
        ("drafts_ready", "Drafts ready for review"),
        ("approved", "Approved"),
        ("dismissed", "Dismissed by user"),
        ("failed", "Generation failed"),
        ("expired", "Date passed without action"),
    ]
    status = models.CharField(max_length=20, choices=STATUS, default="queued")

    posts_generated = models.ManyToManyField(
        "content.Post",
        blank=True,
        related_name="holiday_drafts",
    )

    generation_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-target_date"]
        indexes = [
            models.Index(fields=["user", "target_date"]),
            models.Index(fields=["status"]),
        ]
```

---

## 8. Date Calculation Engine

The engine produces occurrences for any (holiday, year) tuple. Logic lives in `apps/calendar_intel/date_engine.py`.

### 8.1 Fixed dates

```python
def compute_fixed(config: dict, year: int) -> date:
    return date(year, config["month"], config["day"])
```

Examples: Christmas (`{"month": 12, "day": 25}`), New Year (`{"month": 1, "day": 1}`), Rwanda Liberation Day (`{"month": 7, "day": 4}`).

### 8.2 Nth weekday of a month

```python
def compute_nth_weekday(config: dict, year: int) -> date:
    month = config["month"]
    weekday = config["weekday"]   # 0 = Monday, 6 = Sunday
    n = config["n"]                # 1=first, 2=second, ..., -1=last
    cal = calendar.monthcalendar(year, month)
    days = [week[weekday] for week in cal if week[weekday] != 0]
    return date(year, month, days[n - 1] if n > 0 else days[n])
```

Examples: Mother's Day US (`{"month": 5, "weekday": 6, "n": 2}` — 2nd Sunday May), Father's Day US (`{"month": 6, "weekday": 6, "n": 3}`), Thanksgiving (`{"month": 11, "weekday": 3, "n": 4}`).

### 8.3 Easter-relative (Computus algorithm)

```python
def compute_easter(year: int) -> date:
    # Anonymous Gregorian algorithm
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

def compute_easter_offset(config: dict, year: int) -> date:
    return compute_easter(year) + timedelta(days=config["offset_days"])
```

Examples: Easter Sunday (`offset 0`), Good Friday (`offset -2`), Easter Monday (`offset 1`), Ash Wednesday (`offset -46`).

### 8.4 Hijri (Islamic) calendar

Use `hijri-converter` Python package.

```python
from hijri_converter import Hijri, Gregorian

def compute_hijri(config: dict, year: int) -> list[date]:
    """Hijri holidays may straddle the Gregorian year — return all occurrences."""
    h_month = config["hijri_month"]
    h_day = config["hijri_day"]
    occurrences = []
    # Try the current Hijri year and the next, since Hijri years are ~354 days
    for h_year in [_hijri_year_for(year), _hijri_year_for(year) + 1]:
        try:
            g = Hijri(h_year, h_month, h_day).to_gregorian()
            d = date(g.year, g.month, g.day)
            if d.year == year:
                occurrences.append(d)
        except Exception:
            continue
    return occurrences
```

**Important caveats:**
- Hijri dates depend on lunar observation in some traditions; we publish "expected" dates with a `notes` field flagging that the date may shift ±1 day per local observation.
- We surface this in the UI: "Eid al-Fitr — expected April 21, 2026 (date may vary by region)."

Examples: Eid al-Fitr (`hijri_month=10, hijri_day=1`), Eid al-Adha (`hijri_month=12, hijri_day=10`), Mawlid (`hijri_month=3, hijri_day=12`).

### 8.5 Annual rebuild

A Celery beat task `rebuild_holiday_occurrences` runs January 1 each year and:
- Computes occurrences for current year + next year for every active Holiday
- Bulk-creates `HolidayOccurrence` rows
- Deletes occurrences > 2 years in the past

This keeps queries cheap — surfaces just `SELECT * FROM holiday_occurrence WHERE date BETWEEN ? AND ?`.

---

## 9. Holiday Data Sources & Seeding

### 9.1 Primary library

`python-holidays` (PyPI). Covers:
- 100+ countries' statutory holidays
- Multiple regional sub-divisions
- Religious observances per country
- Updated regularly

```python
import holidays
rw = holidays.Rwanda(years=2026)
ke = holidays.Kenya(years=2026)
```

We extract these on first deploy and convert to `Holiday` rows. Re-sync quarterly.

### 9.2 Hijri / Lunar

`hijri-converter` package for Eid al-Fitr, Eid al-Adha, Mawlid, Islamic New Year, Day of Ashura.

### 9.3 Curated supplements

A YAML seed file at `apps/calendar_intel/seeds/curated_moments.yaml` covering:
- Commercial moments (Black Friday, Cyber Monday, Singles' Day)
- Awareness days (World Coffee Day, World Health Day, Earth Day)
- Cultural moments (Valentine's Day where library coverage is weak)
- East African specifics not in `python-holidays` (Saba Saba in Tanzania, Mashujaa Day in Kenya, Liberation Day in Rwanda)

```yaml
- name: "Black Friday"
  slug: black-friday
  date_type: custom_function
  date_config: { function_name: friday_after_thanksgiving }
  countries: []  # global
  category: commercial
  industries: [retail, f_and_b, creative]
  sensitivity_level: safe
  default_relevance_score: 80
  suggested_post_count: 3
  lead_time_days: 14
  tone_hint: urgent
  angles:
    - "Pre-launch: countdown to Black Friday"
    - "Reveal the offer the day before"
    - "Final hours of the deal"

- name: "Liberation Day"
  slug: rwanda-liberation-day
  date_type: fixed
  date_config: { month: 7, day: 4 }
  countries: [RW]
  category: national_holiday
  sensitivity_level: safe
  default_relevance_score: 70
  suggested_post_count: 1
  lead_time_days: 5
  tone_hint: respectful
  angles:
    - "Honor the day with a community message"
    - "Acknowledge employees on this national day"
```

### 9.4 Seed migration

A management command `python manage.py seed_holidays`:
1. Loads from `python-holidays` for target countries (RW, KE, TZ, UG, UG, US, GB initially)
2. Loads Hijri holidays
3. Loads `curated_moments.yaml`
4. Idempotent — safe to re-run

### 9.5 Updates and corrections

- Quarterly: re-sync `python-holidays` to catch updates
- On demand: edit `curated_moments.yaml` and re-run seed for new entries
- Admin UI: lets staff edit Holiday rows directly (correct typos, adjust angles)

---

## 10. Country, Market, and Locale Handling

### 10.1 User country / market data

`User.profile` already has `country` (single value). For Phase 1 this drives the holiday filter.

For Phase 2, we add:

```python
class Profile(models.Model):
    # ... existing fields ...
    primary_country = models.CharField(max_length=2)  # ISO-3166 alpha-2
    secondary_markets = models.JSONField(default=list)  # ["KE", "UG"]
    primary_city = models.CharField(max_length=100, blank=True)
```

### 10.2 Filter logic

```python
def applicable_holidays_for(user) -> QuerySet[Holiday]:
    countries = [user.profile.primary_country] + user.profile.secondary_markets
    return Holiday.objects.filter(
        is_active=True,
    ).filter(
        Q(countries=[]) | Q(countries__overlap=countries)
    ).exclude(
        excluded_countries__overlap=countries,
    )
```

### 10.3 Religion inference

We **do not** ask the user their religion. Instead:

- Country defaults: `RW` → Christmas suggested + Eid suggested (both opt-in for first-week onboarding); `SA` → Eid suggested + Christmas hidden
- A simple `country_religion_defaults.yaml` maps: `country → list of religions to surface as opt-in suggestions`
- The user picks; we never store a religion field

```yaml
RW:  # Rwanda
  - christian   # majority but opt-in nonetheless
  - muslim      # significant minority
KE:
  - christian
  - muslim
SA:  # Saudi Arabia
  - muslim
US:
  - christian
  - jewish
  - secular
```

### 10.4 Locale & currency

- Holiday names render in user's interface language (English first, French/Swahili/Kinyarwanda Phase 3)
- Currency mentions in posts use user's `profile.currency` (already stored)
- Date format follows user's locale

---

## 11. Industry-Specific Moments

### 11.1 Industry taxonomy

Six broad industries in Phase 1, mapped on `Profile.industry`:

| Slug | Examples |
|---|---|
| `retail` | Stores, e-commerce, fashion |
| `f_and_b` | Restaurants, cafés, food brands |
| `services` | Salons, consultants, repair, professional services |
| `b2b` | Software, agencies serving businesses |
| `creative` | Photographers, designers, creators, agencies |
| `health` | Wellness, fitness, healthcare, mental health |

### 11.2 Industry-relevance examples

| Holiday | Retail | F&B | Services | B2B | Creative | Health |
|---|---|---|---|---|---|---|
| Valentine's Day | 95 | 95 | 60 | 20 | 70 | 50 |
| Mother's Day | 90 | 80 | 70 | 30 | 80 | 60 |
| Black Friday | 95 | 60 | 50 | 30 | 70 | 30 |
| Earth Day | 50 | 60 | 50 | 60 | 70 | 70 |
| World Mental Health Day | 30 | 40 | 50 | 50 | 60 | 95 |
| New Year | 80 | 80 | 80 | 80 | 80 | 80 |
| World Coffee Day | 30 | 95 | 30 | 30 | 50 | 30 |

### 11.3 Storage

`Holiday.industries` is a JSON list (`["retail", "f_and_b"]`). Empty list means "all industries." Industry relevance scoring multipliers are computed from a separate matrix in `apps/calendar_intel/relevance.py`:

```python
INDUSTRY_HOLIDAY_BOOSTS = {
    "valentines-day": {"retail": 1.4, "f_and_b": 1.4, "services": 1.0, "b2b": 0.4, "creative": 1.1, "health": 0.8},
    "earth-day":      {"retail": 0.9, "f_and_b": 1.0, "services": 0.9, "b2b": 1.0, "creative": 1.1, "health": 1.1},
    # ... seeded for top 50 holidays ...
}
```

---

## 12. Sensitivity & Opt-In Framework

### 12.1 Three default postures

| Category | Default for new user | Rationale |
|---|---|---|
| `national_holiday` | **Opt-out** (on by default) | Universally celebrated in user's market |
| `religious` | **Opt-in** (off until chosen) | Avoid cross-religious offense |
| `commercial` | **Opt-out** if industry-relevant | Most users want shopping holidays |
| `cultural` | **Opt-out** if `sensitivity_level=safe`, opt-in otherwise | Default safe |
| `awareness_day` | **Suggested but not auto-drafted** | Surface in Brief; user picks if they want a draft |
| `industry_specific` | **Opt-out** if matches user industry | Strongly relevant |
| `personal` | **Always-on for the creator** | Not applicable to others |

### 12.2 Opt-in UI

In onboarding step "Holidays & moments":

```
☐ Christmas (December 25) — observed in your region
☐ Easter (April) — observed in your region
☐ Eid al-Fitr (lunar) — observed in your region
☐ Independence Day (July 4)
─────────────────────────────────
Show me also:
  ☐ Awareness days (World Health Day, Earth Day, etc.)
  ☐ Commercial holidays (Black Friday, etc.)
  ☐ International political days (Pride, Women's Day, etc.)
```

Default checked: national_holiday + commercial (if industry-relevant). Religious unchecked. Political off.

### 12.3 Mute mechanisms

- **Mute this year only:** sets `UserHolidayPreference.muted_until = next_jan_1`
- **Mute permanently:** sets `is_enabled = False`
- **Mute for one occurrence:** sets `HolidayDraft.status = "dismissed"` for that specific draft
- **Restore:** "Reset all holiday preferences" button

### 12.4 Hard guardrails (system-level, not user-controllable)

- Never generate political content for `sensitivity_level = high` holidays unless the user explicitly opts in *and* confirms
- Never generate content that names other religions in a comparative way
- Never use template phrases listed in `Holiday.avoid_phrases`
- Hide all `requires_opt_in=True` holidays from new users for the first 7 days post-signup (let them settle in before pushing sensitive moments)

---

## 13. Relevance Scoring Algorithm

### 13.1 The formula

For each upcoming holiday `H` for user `U`:

```
score = base_relevance(H)
      × industry_multiplier(H, U.industry)
      × country_multiplier(H, U.country, U.markets)
      × user_preference_multiplier(H, U)
      × engagement_history_multiplier(H, U)
      × seasonal_multiplier(date_proximity)

If score >= 60 → eligible for draft generation
If score >= 40 → surface in Brief calendar widget
If score < 40  → ignore
```

### 13.2 Component definitions

```python
def base_relevance(holiday: Holiday) -> float:
    return holiday.default_relevance_score / 100

def industry_multiplier(holiday: Holiday, industry: str) -> float:
    boosts = INDUSTRY_HOLIDAY_BOOSTS.get(holiday.slug, {})
    return boosts.get(industry, 1.0)

def country_multiplier(holiday, country, markets) -> float:
    if holiday.countries == []:
        return 1.0  # global
    if country in holiday.countries:
        return 1.2  # primary market
    if any(m in holiday.countries for m in markets):
        return 1.0  # secondary market
    return 0.0      # not relevant at all

def user_preference_multiplier(holiday, user) -> float:
    pref = user.holiday_preferences.filter(holiday=holiday).first()
    if pref:
        if not pref.is_enabled:
            return 0.0
        if pref.muted_until and pref.muted_until > today():
            return 0.0
        if pref.custom_relevance_score is not None:
            return pref.custom_relevance_score / 100
    return 1.0

def engagement_history_multiplier(holiday, user) -> float:
    """Did past holiday posts perform well for this user?"""
    past_posts = user.posts.filter(
        holiday_drafts__holiday_occurrence__holiday=holiday,
        status="published",
    )
    if not past_posts.exists():
        return 1.0  # no signal
    avg_score = past_posts.aggregate(Avg("engagement_score"))["engagement_score__avg"] or 50
    if avg_score >= 75:
        return 1.3   # past wins boost
    if avg_score < 30:
        return 0.7   # past flops dampen
    return 1.0

def seasonal_multiplier(days_until: int) -> float:
    if days_until <= 0:    return 0.5  # past or today — we're late
    if days_until <= 3:    return 1.2  # very close, raise
    if days_until <= 7:    return 1.1
    if days_until <= 14:   return 1.0
    if days_until <= 30:   return 0.8
    return 0.5
```

### 13.3 Top-N selection per user

Each night the watcher computes scores for all upcoming holidays and picks the top 3 in the next 14-day window. These enter the active draft window.

### 13.4 Tie-breakers

Equal scores → prefer the closer date → prefer the higher base_relevance → alphabetical.

---

## 14. The Holiday Watcher Agent

### 14.1 Schedule

Celery beat task running daily at 02:00 in each user's local timezone.

### 14.2 Pseudocode

```python
@shared_task
def run_holiday_watcher():
    today = timezone.now().date()
    horizon = today + timedelta(days=30)

    for user in User.objects.filter(is_active=True, subscription__includes_holidays=True):
        try:
            process_user(user, today, horizon)
        except Exception as exc:
            logger.exception("Holiday watcher failed for user %s", user.id)


def process_user(user, today, horizon):
    occurrences = HolidayOccurrence.objects.filter(
        date__range=(today, horizon),
        holiday__in=applicable_holidays_for(user),
    ).select_related("holiday")

    scored = []
    for occ in occurrences:
        score = compute_relevance(occ.holiday, user, occ.date - today)
        if score >= 0.4:
            scored.append((score, occ))

    # Process custom events similarly
    for ce in user.custom_events.filter(date__range=(today, horizon), is_active=True):
        scored.append((1.0, ce))

    scored.sort(reverse=True, key=lambda x: x[0])
    top_3 = scored[:3]

    for score, moment in top_3:
        ensure_draft(user, moment, score)


def ensure_draft(user, moment, score):
    target_date = moment.date
    days_until = (target_date - today()).days
    lead_time = moment.holiday.lead_time_days if isinstance(moment, HolidayOccurrence) else moment.lead_time_days

    if days_until > lead_time:
        return  # too early; surface in Brief but don't generate yet

    # Idempotency: don't re-generate if already drafted this year
    existing = HolidayDraft.objects.filter(
        user=user,
        target_date=target_date,
        holiday_occurrence=moment if isinstance(moment, HolidayOccurrence) else None,
        custom_event=moment if isinstance(moment, CustomEvent) else None,
    ).first()
    if existing and existing.status in ("queued", "generating", "drafts_ready", "approved"):
        return

    draft = HolidayDraft.objects.create(
        user=user,
        target_date=target_date,
        relevance_score=int(score * 100),
        holiday_occurrence=moment if isinstance(moment, HolidayOccurrence) else None,
        custom_event=moment if isinstance(moment, CustomEvent) else None,
    )
    generate_holiday_drafts.delay(draft.id)
```

### 14.3 Idempotency

Each `(user, holiday_occurrence)` and `(user, custom_event, target_date)` is unique. The agent checks existence before generating. A user dismissing a draft sets status `dismissed`, which prevents regeneration.

### 14.4 User-local timezone

The watcher runs at 02:00 user-local using a Celery beat schedule that fans out per-timezone. We already do this for the Daily Brief — same pattern.

---

## 15. Content Generation Pipeline

### 15.1 The prompt template

```
You are Kova's holiday content generator. Write 2 distinct social media post
drafts for the following moment, in the user's brand voice.

Business: {business_name}
Brand voice: {brand_voice}
Industry: {industry}
Location: {city}, {country}
Currency: {currency}
Top recent products: {top_3_products}
Top recent posts (for tone calibration): {top_2_posts}

Moment: {holiday_name}
Date: {date} ({days_until} days from today)
Tone hint: {tone_hint}
Suggested angles: {angles}

HARD RULES:
- Tie the post to the user's actual product or service. Be specific.
- Use brand voice exactly. Match recent successful posts in tone.
- Do NOT use these phrases: {avoid_phrases}
- Do NOT fabricate offers, discounts, or testimonials.
- For religious moments: respectful, never proselytizing.
- For political moments: neutral, never partisan.
- Each draft must use a different angle from the list above.

Per-platform conventions:
- Instagram: 1-2 sentences + 3-5 hashtags + emojis OK
- LinkedIn: 3-4 sentences, professional tone, no hashtag spam
- Twitter/X: under 280 chars, 1-2 hashtags max
- Facebook: 2-3 sentences, conversational

Return JSON:
{
  "drafts": [
    {
      "angle_used": "...",
      "platform_versions": {
        "instagram": "...",
        "linkedin": "...",
        "twitter": "...",
        "facebook": "..."
      },
      "suggested_publish_time": "ISO datetime",
      "rationale": "1 sentence why this angle"
    }
  ]
}
```

### 15.2 Tool-use for structured output

Same pattern as the website generator: define a `submit_holiday_drafts` tool with strict schema, force the model to call it.

### 15.3 Draft storage

For each platform version, create a `Post` row with:
- `status = "pending_approval"`
- `scheduled_at = suggested_publish_time` (the day of the holiday, optimal hour from user's analytics)
- `holiday_drafts.add(draft)`

### 15.4 Suggested publish time

Pick the best time from `user.posting_analytics` for that platform. If no signal, default to 10:00 user-local for evening platforms, 09:00 for morning platforms.

For commercial holidays (Black Friday): publish multiple posts across the day (morning teaser, midday push, evening last-call).

### 15.5 Quality gates

Before saving drafts:
- Length check per platform
- Banned-phrase scan against `Holiday.avoid_phrases`
- Brand voice similarity check (compare to user's last 5 published posts using simple cosine similarity on embeddings)
- Sensitivity scan (flag if generated text contains political/religious terms not in the holiday's allowed set)

If any check fails: regenerate once with stricter prompt; if still fails, mark draft `failed` and notify user via Brief.

---

## 16. Custom Events

### 16.1 Use cases

- "Our 2nd anniversary" (yearly)
- "Product X launch — March 15" (once)
- "Founder's birthday — July 21" (yearly, optional)
- "Anniversary of first 100 customers" (yearly)
- "Monthly customer appreciation day" (monthly)

### 16.2 Creation flow

User clicks "Add custom event" in Calendar app or Holiday Settings:

```
┌────────────────────────────────────────────────┐
│ Add a custom moment                             │
│                                                  │
│ Name:        [ Our 2nd Anniversary           ]  │
│ Description: [ Founded 2024-05-15            ]  │
│ Date:        [ 2026-05-15                    ]  │
│ Recurrence:  [ ◉ Yearly  ○ Once  ○ Monthly  ]  │
│                                                  │
│ ▾ Advanced                                       │
│   Tone:        [ celebratory               ▼]  │
│   Lead time:   [ 5 days                      ]  │
│   Posts:       [ 2                           ]  │
│   ☑ Auto-draft posts                            │
│                                                  │
│   Suggested angles:                              │
│   [ Reflect on the journey               ]      │
│   [ Thank loyal customers                ]      │
│   [ Tease what's next                    ]      │
│   [ + add angle ]                                │
│                                                  │
│              [ Cancel ]  [ Save ]                │
└────────────────────────────────────────────────┘
```

### 16.3 Recurrence handling

Yearly events expand into `HolidayOccurrence`-like rows annually via the same nightly job. Once-only events are processed once and then deactivated.

### 16.4 Privacy

Custom events are scoped to the user; never visible to other users or in any aggregate.

---

## 17. Integration with Daily Brief

### 17.1 Calendar widget

A new section in the Brief sidebar:

```
┌──────────────────────────────────┐
│ COMING UP                         │
│                                   │
│ 🎁 Mother's Day                  │
│    in 9 days · 2 drafts ready    │
│    [ Review drafts → ]            │
│                                   │
│ ⚡ Black Friday                  │
│    in 18 days                     │
│    [ Plan campaign → ]            │
│                                   │
│ 🌍 Liberation Day                │
│    in 25 days                     │
└──────────────────────────────────┘
```

### 17.2 Brief summary integration

When a holiday is in the active draft window, the LLM generating the brief summary gets:

```
HOLIDAY CONTEXT:
- Mother's Day is in 9 days. 2 drafts have been prepared.
- Suggest the user review drafts in their morning routine.
```

The third paragraph of the brief ("Your move today") may incorporate it: *"Your move today: review the two Mother's Day drafts I've prepared — they go out in 9 days."*

### 17.3 Acknowledgment chip

When a holiday is happening today, the brief opens with:

```
"Marie, today is World Coffee Day — and your café posted twice last
year and got 3× normal engagement. I've drafted a post tied to your
new winter blend; review when you have a moment."
```

This reflects history, ties to product, and feels intelligent rather than templated.

---

## 18. Integration with Content Studio

### 18.1 Filter chip

Add to existing studio filter bar:

```
[ All ] [ Pending ] [ Scheduled ] [ Published ] [ 🎉 Holiday drafts (3) ]
```

Clicking opens a grouped view:

```
🎁 Mother's Day — May 14
   ┌─────────────┐ ┌─────────────┐
   │ Draft 1     │ │ Draft 2     │
   │ (Instagram) │ │ (LinkedIn)  │
   └─────────────┘ └─────────────┘

⚡ Black Friday — Nov 28
   [ ... ]
```

### 18.2 Bulk approve

A "Approve all for [Mother's Day]" button schedules every draft for the optimal time on the date.

### 18.3 Per-draft actions

Same as regular posts: edit, regenerate, schedule manually, reject. Plus:
- "Generate another angle" — picks a different angle from `Holiday.angles`
- "Use my own angle" — opens a textarea: *"What angle should this post take?"*

---

## 19. Integration with Calendar App

### 19.1 Visual markers

Calendar grid shows colored dots/badges per holiday:

```
        Mon    Tue    Wed    Thu    Fri    Sat    Sun
        12     13     14🎁   15     16     17     18
                      [3]
                Mother's
                  Day
```

Click the badge → side panel showing drafts + actions.

### 19.2 Right-click → "Generate post for this day"

User can manually request a post for any date even if no holiday is registered — the prompt receives "User specifically wants content for {date}" without holiday context.

---

## 20. Integration with Website Generator

### 20.1 Seasonal CTA banner

When a Tier-A holiday (Mother's Day, Christmas, Black Friday) is in the active window, the user's website CTA banner section auto-updates:

```python
# In apps/websites/tasks.py
def maybe_seasonal_refresh(website):
    upcoming = HolidayDraft.objects.filter(
        user=website.user,
        target_date__range=(today(), today() + timedelta(days=14)),
        relevance_score__gte=80,
    ).order_by("-relevance_score").first()

    if not upcoming:
        return

    # Regenerate just the cta_banner section with holiday context
    new_banner = generate_section(
        website, "cta_banner",
        intent=f"Make this banner about the upcoming {upcoming.holiday_name}",
    )
    website.sections["cta_banner"] = new_banner
    deploy_website(website.id, sections_only=["cta_banner"])
```

### 20.2 Reverts after the date

24 hours after the holiday passes, the banner reverts to the user's standard banner. Tracked via `WebsiteGenerationLog` so we know what to revert to.

---

## 21. Onboarding Flow

### 21.1 New onboarding step

Inserted between brand voice and first post generation:

```
┌──────────────────────────────────────────────────────────┐
│ Step 4 of 6 — Holidays & cultural moments                │
│                                                            │
│ Kova will help you stay ahead of the moments your         │
│ customers care about. Pick which apply to you.            │
│                                                            │
│ Suggested for {country}:                                  │
│  ☑ National holidays (Independence Day, Liberation Day)   │
│  ☐ Christmas / Easter                                     │
│  ☐ Eid al-Fitr / Eid al-Adha                             │
│                                                            │
│ Commercial moments (industry: {industry}):                │
│  ☑ Mother's Day, Father's Day                            │
│  ☑ Valentine's Day                                        │
│  ☑ Black Friday                                           │
│                                                            │
│ Want to add your own?                                     │
│  [ + Add a custom moment ]                                │
│                                                            │
│              [ Skip ]      [ Save & continue ]            │
└──────────────────────────────────────────────────────────┘
```

### 21.2 Default suggestions algorithm

Based on `country` + `industry`:
- Pre-check national holidays (always relevant)
- Pre-check industry-relevant commercial moments
- Show religious holidays as unchecked options
- Show political/awareness days as opt-in only

### 21.3 Skipping

User can skip; defaults apply (national holidays only). They can revisit any time at `/calendar/preferences/`.

---

## 22. User Preference UI

### 22.1 Main preferences page

`/calendar/preferences/`

```
┌──────────────────────────────────────────────────────────┐
│ Holidays & Moments                                        │
│                                                            │
│ Markets you serve:                                        │
│   Primary: [ Rwanda ▼ ]                                   │
│   Also:    [ Kenya ✕ ] [ Uganda ✕ ] [ + Add ]            │
│                                                            │
│ Categories:                                               │
│   ☑ National holidays     ☑ Commercial / shopping        │
│   ☐ Religious             ☐ Political / awareness        │
│   ☑ Industry-specific     ☑ My custom events             │
│                                                            │
│ ─────────────────────────────────────────────────         │
│ All upcoming moments:                                     │
│                                                            │
│ ☑ Mother's Day        May 12    ⓘ relevance 92%          │
│ ☑ Liberation Day      Jul 4     ⓘ relevance 70%          │
│ ☐ Eid al-Adha         Jun 6     ⓘ opt-in                 │
│ ✕ Valentine's Day     Feb 14    Muted: this year only    │
│                                                            │
│ [ + Add custom event ]                                    │
└──────────────────────────────────────────────────────────┘
```

### 22.2 Per-holiday detail page

Click any row → modal:

```
Mother's Day
─────────────
☑ Enabled
Lead time:    [ 7 days  ▼ ]
Post count:   [ 2       ▼ ]
☑ Auto-draft posts (require my approval)

Suggested angles for your industry (retail):
  • Honor the moms in your community
  • A discount for Mom this year
  • Behind-the-scenes from your team's moms
  + add your own angle

Past performance: 1 post, 240 engagements (your avg: 80)

[ Mute this year ]   [ Mute permanently ]   [ Save ]
```

---

## 23. Notifications

### 23.1 Triggers

| Event | Channel | Timing |
|---|---|---|
| Drafts ready for approval | In-app + Daily Brief | When `HolidayDraft.status` → `drafts_ready` |
| Holiday is tomorrow + drafts exist | Push (if enabled) | 18:00 day before |
| Holiday is today + no drafts approved | Daily Brief | Morning of |
| Generation failed | Daily Brief | Same day as failure |

### 23.2 Push notification examples

```
🎁 Mother's Day drafts ready
   2 posts in your voice — review when you have a moment.

⚡ Black Friday is in 7 days
   I've drafted your campaign — let's go.
```

### 23.3 Anti-fatigue

Maximum one holiday push per day per user. Multiple holidays in same week are batched into the daily brief, not individual pushes.

---

## 24. URL Routes & API Endpoints

```python
# apps/calendar_intel/urls.py
app_name = "calendar_intel"

urlpatterns = [
    # Preferences
    path("preferences/", views.preferences, name="preferences"),
    path("preferences/<int:holiday_id>/", views.holiday_preference, name="holiday_preference"),

    # Custom events
    path("custom/", views.custom_event_list, name="custom_event_list"),
    path("custom/add/", views.custom_event_add, name="custom_event_add"),
    path("custom/<int:event_id>/edit/", views.custom_event_edit, name="custom_event_edit"),
    path("custom/<int:event_id>/delete/", views.custom_event_delete, name="custom_event_delete"),

    # Drafts
    path("drafts/", views.drafts_list, name="drafts_list"),
    path("drafts/<int:draft_id>/", views.draft_detail, name="draft_detail"),
    path("drafts/<int:draft_id>/regenerate/", views.draft_regenerate, name="draft_regenerate"),
    path("drafts/<int:draft_id>/dismiss/", views.draft_dismiss, name="draft_dismiss"),

    # HTMX endpoints
    path("htmx/upcoming/", views.htmx_upcoming, name="htmx_upcoming"),
    path("htmx/calendar-widget/", views.htmx_calendar_widget, name="htmx_calendar_widget"),
    path("htmx/preference-toggle/<int:holiday_id>/", views.htmx_preference_toggle, name="htmx_preference_toggle"),
]
```

---

## 25. Django Application Structure

```
apps/calendar_intel/
├── __init__.py
├── apps.py
├── admin.py
├── urls.py
├── views.py
├── models.py
├── forms.py
├── signals.py
├── date_engine.py        # Date computation (fixed, nth-weekday, Easter, Hijri)
├── relevance.py          # Scoring algorithm + industry boost matrix
├── seeds/
│   ├── curated_moments.yaml
│   ├── country_religion_defaults.yaml
│   └── industry_holiday_boosts.yaml
├── seed_loader.py        # Loads YAML + python-holidays into DB
├── management/
│   └── commands/
│       ├── seed_holidays.py
│       ├── rebuild_occurrences.py
│       └── run_holiday_watcher_now.py  # for testing
├── tasks.py              # Celery: watcher, generator, occurrence rebuild
├── prompts.py            # Prompts for Claude
├── schemas.py            # Pydantic schemas for draft outputs
├── tests/
│   ├── test_date_engine.py
│   ├── test_relevance.py
│   ├── test_watcher.py
│   ├── test_generator.py
│   └── test_integration.py
└── migrations/

templates/calendar_intel/
├── preferences.html
├── drafts_list.html
├── draft_detail.html
├── custom_event_form.html
└── partials/
    ├── _calendar_widget.html
    ├── _holiday_row.html
    └── _draft_card.html
```

---

## 26. Failure Modes & Mitigations

| Failure | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Hijri date off by ±1 day | Certain | Low | Surface in UI: "date may vary by region"; allow user override |
| python-holidays missing a Rwandan holiday | Possible | Medium | Curated supplements override library; quarterly review |
| Watcher generates duplicates | Low | Medium | Idempotency check on (user, occurrence) before generating |
| Draft generation fails for one user | Possible | Low | Catch and continue to next user; log error; surface in Brief |
| Brand voice produces tone-deaf holiday post | Possible | High | Quality gates + sensitivity scan + always-draft (never publish) |
| Religious holiday surfaced to wrong user | Possible | High | Strict opt-in; never auto-include in defaults |
| Custom event recurrence breaks across leap years | Low | Low | Use rrule library or carefully test Feb 29 |
| User changes country mid-cycle, drafts are stale | Possible | Low | On country change, re-run watcher within 1 hour; mark old drafts expired |
| LLM API quota exceeded during peak holiday season | Likely Q4 | High | Pre-generate Black Friday / Christmas drafts in October; rate-limit per-user |
| Watcher doesn't run because Celery worker down | Low | High | Health check; if no run in 24h, page on-call |

---

## 27. Pricing & Plan Tiers

| Plan | Holiday awareness? | Auto-drafts? | Custom events? | Markets supported |
|---|---|---|---|---|
| Free / Trial | View calendar widget | No | 1 | Primary only |
| Starter | View + manual draft request | Limited (5/mo) | 5 | Primary only |
| Growth | Full | Unlimited | 20 | Primary + 2 secondary |
| Scale | Full + early access to upcoming holidays (60-day horizon) | Unlimited | Unlimited | Unlimited |
| Enterprise | + Custom holiday curation by Kova team | Unlimited | Unlimited | Unlimited |

---

## 28. Implementation Roadmap

### Phase 1 — Core Engine (2 weeks)

**Week 1**
- [ ] Create `apps/calendar_intel/` with models + migrations
- [ ] Date engine: fixed, nth-weekday, Easter, Hijri
- [ ] Seed loader + `seed_holidays` command
- [ ] Curated YAML: 100+ holidays seeded for RW, KE, TZ, UG + global
- [ ] `rebuild_occurrences` for current + next year
- [ ] Admin UI: Holiday browse + edit
- [ ] Unit tests for date engine

**Week 2**
- [ ] Relevance scoring algorithm + tests
- [ ] Daily Brief integration: calendar widget showing top 3 upcoming
- [ ] User preferences page (basic: enable/disable per holiday)
- [ ] Country-based filtering
- [ ] Onboarding step: holiday opt-in
- [ ] Soft launch — visible in Brief, no drafts yet

### Phase 2 — Auto-Drafting (2 weeks)

**Week 3**
- [ ] Holiday watcher Celery task
- [ ] `HolidayDraft` model + state machine
- [ ] Content generator with brand voice + holiday context
- [ ] Pydantic schema for draft output
- [ ] Quality gates: length, banned phrases, sensitivity
- [ ] Drafts surface in Content Studio with filter chip

**Week 4**
- [ ] Per-holiday detail page (angles, lead time, post count)
- [ ] "Generate another angle" + "Use my own angle"
- [ ] Push notifications for ready drafts
- [ ] Daily Brief enhanced: drafts callout in summary

### Phase 3 — Custom & Polish (1 week)

**Week 5**
- [ ] Custom events model + UI
- [ ] Calendar app integration (markers + side panel)
- [ ] Past-performance tracking (engagement on prior holiday posts)
- [ ] Industry-boost matrix tuning based on early data
- [ ] Mute mechanisms (this year, permanently, single occurrence)

### Phase 4 — Advanced (later)

- [ ] Multi-market support (secondary countries surfaced as opt-in)
- [ ] Trend-day detection (viral days from real-time signals)
- [ ] Website CTA banner seasonal refresh
- [ ] Localized holiday names (Kinyarwanda, French, Swahili)
- [ ] Bulk campaign mode for retail (3-day Black Friday sequences)

---

## 29. Open Questions

1. **Religion: country-default suggestion or onboarding question?** Recommendation: country-default suggestions; never store religion as a field. Confirm during implementation.
2. **Multi-market support: Phase 1 or Phase 4?** Recommendation: Phase 4. Phase 1 = primary country only, validate first.
3. **Hijri date observation:** Display "expected date" with caveat, or fetch from a regional Islamic authority API? Phase 1 = computed + caveat; Phase 4 = optionally per-region.
4. **What happens to a draft if the holiday passes?** Mark as `expired`; archive but don't delete (audit trail).
5. **Should past holiday posts feed back into engagement_history_multiplier even if user deleted them?** Yes — keep counts at the `HolidayDraft` level.
6. **How many days before a holiday do we lock the draft?** None — user can edit/regenerate up to publish time.
7. **Should holiday drafts respect the user's content calendar (e.g., not double-up on a day already full)?** Yes Phase 2 — check posting density on target_date and shift if needed.
8. **What's the export format if a user wants to "see all my upcoming moments as ICS"?** Phase 4: provide an iCalendar feed URL per user for syncing to Google Calendar.
9. **Industry classification: where does it live?** `Profile.industry` (already exists). If not granular enough, add subcategory in Phase 2.
10. **Do we charge for early access to next year's drafts?** Phase 4; Scale tier gets 60-day horizon vs. Growth's 30-day.

---

## 30. Glossary

- **Moment:** Any holiday, observance, or custom event significant to a user. Used as an umbrella term.
- **Occurrence:** A specific instantiation of a holiday on a specific date in a specific year.
- **Active draft window:** The period (default: 7 days before) when a moment is eligible for draft generation.
- **Watcher agent:** The nightly Celery task that scans for upcoming moments and triggers draft generation.
- **Industry boost:** Multiplier applied to relevance score based on user's industry × holiday match.
- **Sensitivity level:** A holiday's risk classification (`safe`, `consider`, `high`) used for opt-in defaults.
- **Lead time:** Days before the holiday at which we generate drafts.
- **Curated supplements:** YAML-loaded holidays that aren't in `python-holidays` (e.g., commercial days, regional specifics).
- **Tier-A holiday:** Score ≥ 80 for the user; eligible for website CTA banner refresh.
- **Mute (this year):** Disable a holiday for the current year only; auto-restores next year.
- **Mute (permanent):** Disable until user explicitly re-enables.

---

## Appendix A: Sample Pydantic Schema

```python
# apps/calendar_intel/schemas.py
from pydantic import BaseModel, Field
from typing import Optional

class PlatformVersions(BaseModel):
    instagram: Optional[str] = Field(None, max_length=2200)
    linkedin: Optional[str] = Field(None, max_length=3000)
    twitter: Optional[str] = Field(None, max_length=280)
    facebook: Optional[str] = Field(None, max_length=63206)

class HolidayDraftItem(BaseModel):
    angle_used: str = Field(..., max_length=200)
    platform_versions: PlatformVersions
    suggested_publish_time: str  # ISO datetime
    rationale: str = Field(..., max_length=300)

class HolidayDraftsOutput(BaseModel):
    drafts: list[HolidayDraftItem] = Field(..., min_length=1, max_length=4)
```

---

## Appendix B: Sample seed YAML entry

```yaml
- name: "Mother's Day (US/Global)"
  slug: mothers-day
  short_description: "Day to honor mothers and mother figures"
  date_type: nth_weekday
  date_config: { month: 5, weekday: 6, n: 2 }  # 2nd Sunday May
  countries: []   # global with regional variations elsewhere
  category: cultural
  religion: ""
  industries: [retail, f_and_b, services, creative, health]
  sensitivity_level: safe
  default_relevance_score: 80
  suggested_post_count: 2
  lead_time_days: 9
  tone_hint: warm
  angles:
    - "Honor the moms in your community with a specific story"
    - "A meaningful gift idea tied to your product/service"
    - "Behind-the-scenes from a mother on your team"
    - "Discount or special offer for the day"
  avoid_phrases:
    - "Happy Mother's Day to all the moms!"
    - "Celebrating the special woman in your life"
    - "On this special day"
```

---

## Appendix C: Smoke test — one holiday end-to-end

Manual test sequence after Phase 2 build:

```bash
# 1. Seed
python manage.py seed_holidays
python manage.py rebuild_occurrences

# 2. Pick a test user with country=RW, industry=f_and_b
# 3. Manually advance system clock to 9 days before Mother's Day:
TEST_DATE=2026-05-03 python manage.py run_holiday_watcher_now

# Expected:
# - HolidayDraft created for that user × Mother's Day occurrence
# - 2 Post drafts created in Content Studio
# - Daily Brief shows "Mother's Day in 9 days — 2 drafts ready"
# - User can review, edit, approve, or dismiss
```

---

## Document maintenance

This document is the source of truth for the Holiday Awareness system. Updates:

- **Major changes:** Update doc and bump date in header.
- **Adding a new holiday or correcting one:** Edit `seeds/curated_moments.yaml` and re-seed.
- **Adding a new industry:** Update `industries` taxonomy here + matrix in relevance.py.
- **Decisions on Open Questions:** Move from Section 29 into the relevant prior section.

When in doubt, this doc wins over Slack and tickets.

---

*End of specification.*
