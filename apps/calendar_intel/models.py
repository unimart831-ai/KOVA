"""
Calendar Intelligence — Holidays & Cultural Moments models.

See KOVA_HOLIDAY_AWARENESS.md (root) for the full spec. Section 7 covers data
models; this module implements all five entities exactly as specified there.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Holiday(models.Model):
    """Master record for a recognized holiday or cultural moment.
    Occurrences are computed by the date engine (see date_engine.py)."""

    class DateType(models.TextChoices):
        FIXED = "fixed", "Fixed (same date every year)"
        NTH_WEEKDAY = "nth_weekday", "Nth weekday of a month"
        COMPUTED_EASTER = "computed_easter", "Computed from Easter"
        LUNAR_ISLAMIC = "lunar_islamic", "Hijri lunar calendar"
        LUNAR_CHINESE = "lunar_chinese", "Chinese lunar calendar"
        CUSTOM_FUNCTION = "custom_function", "Custom date function"

    class Category(models.TextChoices):
        NATIONAL = "national_holiday", "National / statutory holiday"
        RELIGIOUS = "religious", "Religious observance"
        COMMERCIAL = "commercial", "Commercial / shopping holiday"
        CULTURAL = "cultural", "Cultural moment"
        AWARENESS = "awareness_day", "Awareness day"
        INDUSTRY = "industry_specific", "Industry-specific moment"
        PERSONAL = "personal", "Personal / business event"

    class Religion(models.TextChoices):
        CHRISTIAN = "christian", "Christian"
        MUSLIM = "muslim", "Muslim"
        HINDU = "hindu", "Hindu"
        BUDDHIST = "buddhist", "Buddhist"
        JEWISH = "jewish", "Jewish"
        SECULAR = "secular", "Secular"
        NONE = "", "None / not applicable"

    class Sensitivity(models.TextChoices):
        SAFE = "safe", "Safe — broad audience, low risk"
        CONSIDER = "consider", "Consider — depends on market context"
        HIGH = "high", "High — politically/religiously charged, requires opt-in"

    class Tone(models.TextChoices):
        WARM = "warm", "Warm / heartfelt"
        CELEBRATORY = "celebratory", "Celebratory / festive"
        RESPECTFUL = "respectful", "Respectful / reverent"
        PLAYFUL = "playful", "Playful / fun"
        URGENT = "urgent", "Urgent / commercial"
        INFORMATIVE = "informative", "Informative / educational"
        NONE = "", "Unspecified"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True)
    short_description = models.CharField(max_length=500, blank=True)

    # Date logic
    date_type = models.CharField(max_length=20, choices=DateType.choices)
    date_config = models.JSONField(
        default=dict,
        help_text=(
            "Date computation config. Examples:\n"
            "  fixed: {'month': 12, 'day': 25}\n"
            "  nth_weekday: {'month': 5, 'weekday': 6, 'n': 2}  (2nd Sunday May)\n"
            "  computed_easter: {'offset_days': -2}  (Good Friday)\n"
            "  lunar_islamic: {'hijri_month': 10, 'hijri_day': 1}  (Eid al-Fitr)\n"
            "  custom_function: {'function_name': 'friday_after_thanksgiving'}"
        ),
    )

    # Geographic scope — empty list means global
    countries = models.JSONField(
        default=list, blank=True,
        help_text="ISO-3166-1 alpha-2 codes. ['RW', 'KE'] for East Africa, [] for global.",
    )
    excluded_countries = models.JSONField(
        default=list, blank=True,
        help_text="Countries to exclude from a global holiday (rare).",
    )

    category = models.CharField(max_length=30, choices=Category.choices)
    religion = models.CharField(
        max_length=30, choices=Religion.choices, default=Religion.NONE, blank=True,
    )
    industries = models.JSONField(
        default=list, blank=True,
        help_text="Industry slugs the holiday is most relevant to. Empty = all industries.",
    )

    sensitivity_level = models.CharField(
        max_length=20, choices=Sensitivity.choices, default=Sensitivity.SAFE,
    )
    requires_opt_in = models.BooleanField(default=False)

    default_relevance_score = models.IntegerField(
        default=50,
        help_text="Base relevance 0-100. Multiplied by industry/country/preference factors.",
    )
    suggested_post_count = models.PositiveIntegerField(default=2)
    lead_time_days = models.PositiveIntegerField(
        default=7,
        help_text="How many days before the date drafts should be generated.",
    )

    tone_hint = models.CharField(
        max_length=50, choices=Tone.choices, default=Tone.NONE, blank=True,
    )
    angles = models.JSONField(
        default=list, blank=True,
        help_text="Suggested content angles. List of short strings.",
    )
    avoid_phrases = models.JSONField(
        default=list, blank=True,
        help_text="Phrases the generator must avoid (anti-generic guardrail).",
    )

    is_active = models.BooleanField(default=True)
    source = models.CharField(
        max_length=100, blank=True,
        help_text="Origin of this entry: 'python-holidays', 'curated', 'admin', etc.",
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["religion"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    @property
    def is_global(self) -> bool:
        return not self.countries

    def applies_to_country(self, code: str) -> bool:
        if not code:
            return self.is_global
        if code in (self.excluded_countries or []):
            return False
        if self.is_global:
            return True
        return code in (self.countries or [])


class HolidayOccurrence(models.Model):
    """Pre-computed occurrence of a Holiday for a specific year.
    Populated by the rebuild_occurrences command — one row per (holiday, year)."""

    holiday = models.ForeignKey(
        Holiday, on_delete=models.CASCADE, related_name="occurrences",
    )
    year = models.PositiveIntegerField()
    date = models.DateField()
    notes = models.CharField(
        max_length=200, blank=True,
        help_text="Caveats specific to this occurrence (e.g., 'date may shift ±1 by region').",
    )

    class Meta:
        unique_together = [("holiday", "year")]
        ordering = ["date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["year", "date"]),
        ]

    def __str__(self):
        return f"{self.holiday.name} — {self.date.isoformat()}"


class UserHolidayPreference(models.Model):
    """Per-user override for a Holiday. Absence = use Holiday defaults filtered
    by the user's country/industry."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="holiday_preferences",
    )
    holiday = models.ForeignKey(Holiday, on_delete=models.CASCADE)

    is_enabled = models.BooleanField(default=True)
    custom_relevance_score = models.IntegerField(null=True, blank=True)
    custom_lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    custom_post_count = models.PositiveIntegerField(null=True, blank=True)
    auto_draft_posts = models.BooleanField(default=True)

    muted_until = models.DateField(
        null=True, blank=True,
        help_text="If set, holiday is muted until this date. Used for 'mute this year only'.",
    )

    notes = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "holiday")]

    def __str__(self):
        state = "enabled" if self.is_enabled else "disabled"
        return f"{self.user} · {self.holiday.name} ({state})"

    def is_currently_muted(self) -> bool:
        if not self.is_enabled:
            return True
        if self.muted_until and self.muted_until > timezone.now().date():
            return True
        return False


class CustomEvent(models.Model):
    """User-defined personal or business moments (anniversaries, launches, etc.)."""

    class Recurrence(models.TextChoices):
        ONCE = "once", "One-time"
        YEARLY = "yearly", "Annually on this date"
        MONTHLY = "monthly", "Monthly"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custom_events",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    date = models.DateField()
    recurrence = models.CharField(
        max_length=20, choices=Recurrence.choices, default=Recurrence.YEARLY,
    )

    tone_hint = models.CharField(
        max_length=50, choices=Holiday.Tone.choices,
        default=Holiday.Tone.CELEBRATORY, blank=True,
    )
    angles = models.JSONField(default=list, blank=True)
    suggested_post_count = models.PositiveIntegerField(default=1)
    lead_time_days = models.PositiveIntegerField(default=3)

    is_active = models.BooleanField(default=True)
    auto_draft_posts = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.date.isoformat()})"


class HolidayDraft(models.Model):
    """Tracks a draft cycle for a moment + user. Prevents duplicate generation
    and provides audit visibility."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued for generation"
        GENERATING = "generating", "Generating"
        DRAFTS_READY = "drafts_ready", "Drafts ready for review"
        APPROVED = "approved", "Approved"
        DISMISSED = "dismissed", "Dismissed by user"
        FAILED = "failed", "Generation failed"
        EXPIRED = "expired", "Date passed without action"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="holiday_drafts",
    )

    # Exactly one of these is set
    holiday_occurrence = models.ForeignKey(
        HolidayOccurrence, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="drafts",
    )
    custom_event = models.ForeignKey(
        CustomEvent, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="drafts",
    )

    target_date = models.DateField()
    relevance_score = models.IntegerField(default=0)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED,
    )

    # Posts created from this draft cycle (Phase 2 — populated when generation runs)
    posts_generated = models.ManyToManyField(
        "content.Post", blank=True, related_name="holiday_drafts",
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
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(holiday_occurrence__isnull=False, custom_event__isnull=True)
                    | models.Q(holiday_occurrence__isnull=True, custom_event__isnull=False)
                ),
                name="holidaydraft_exactly_one_moment",
            ),
        ]

    def __str__(self):
        moment = self.holiday_occurrence or self.custom_event
        return f"{self.user} · {moment} · {self.status}"

    @property
    def moment_name(self) -> str:
        if self.holiday_occurrence:
            return self.holiday_occurrence.holiday.name
        if self.custom_event:
            return self.custom_event.name
        return "(unknown)"
