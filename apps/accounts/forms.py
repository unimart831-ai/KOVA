from django import forms

from apps.accounts.models import User, UserProfile
from apps.accounts.phone_utils import apply_phone_to_user, is_valid_phone, normalize_phone


class KovaSignupForm(forms.Form):
    """Signup form — phone required so we can reach users via WhatsApp/SMS."""

    phone_number = forms.CharField(
        max_length=20,
        label="Phone number",
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "07XX XXX XXX",
            "autocomplete": "tel",
        }),
        help_text="For onboarding updates, support, and WhatsApp briefs.",
    )

    def clean_phone_number(self):
        phone = normalize_phone(self.cleaned_data.get("phone_number", ""))
        if not phone:
            raise forms.ValidationError("Phone number is required.")
        if not is_valid_phone(phone):
            raise forms.ValidationError(
                "Enter a valid phone number (Kenyan 07xx/01xx/02xx or international +country code)."
            )
        return phone

    def signup(self, request, user):
        apply_phone_to_user(user, self.cleaned_data["phone_number"])
        return user


class PhoneCaptureForm(forms.Form):
    """Collect phone for OAuth signups that skipped the email signup form."""

    phone_number = forms.CharField(
        max_length=20,
        label="Phone number",
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "07XX XXX XXX",
            "autocomplete": "tel",
        }),
        help_text="We use this for setup updates, support, and optional WhatsApp briefs.",
    )

    def clean_phone_number(self):
        phone = normalize_phone(self.cleaned_data.get("phone_number", ""))
        if not phone:
            raise forms.ValidationError("Phone number is required.")
        if not is_valid_phone(phone):
            raise forms.ValidationError(
                "Enter a valid phone number (Kenyan 07xx/01xx/02xx or international +country code)."
            )
        return phone


class UserSettingsForm(forms.ModelForm):
    phone_number = forms.CharField(
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "0712345678",
            "autocomplete": "tel",
        }),
        help_text="For WhatsApp daily brief pings (Pro plan). Kenyan format 07xx…",
    )

    class Meta:
        model = User
        fields = [
            "full_name", "timezone", "daily_brief_time", "phone_number",
            "brief_email_enabled", "brief_whatsapp_enabled",
            "money_board_digest_enabled", "avatar",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "input", "placeholder": "Your full name"}),
            "timezone": forms.Select(attrs={"class": "input"}),
            "daily_brief_time": forms.TimeInput(attrs={"class": "input", "type": "time"}),
            "brief_email_enabled": forms.CheckboxInput(attrs={"class": "rounded border-gray-300 text-kova-600 focus:ring-kova-500"}),
            "brief_whatsapp_enabled": forms.CheckboxInput(attrs={"class": "rounded border-gray-300 text-kova-600 focus:ring-kova-500"}),
            "money_board_digest_enabled": forms.CheckboxInput(attrs={"class": "rounded border-gray-300 text-kova-600 focus:ring-kova-500"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.timezones import CURATED_TIMEZONES
        from apps.billing.models import get_user_plan_limits

        choices = [(tz, tz.replace("_", " ")) for tz in CURATED_TIMEZONES]
        current = ""
        if self.instance and getattr(self.instance, "timezone", None):
            current = self.instance.timezone
        if current and current not in CURATED_TIMEZONES:
            choices.insert(0, (current, f"{current} (current)"))
        self.fields["timezone"].widget = forms.Select(
            choices=choices,
            attrs={"class": "input"},
        )

        if self.instance and self.instance.pk:
            limits = get_user_plan_limits(self.instance)
            if not limits.get("email_brief"):
                self.fields["brief_email_enabled"].disabled = True
            if not limits.get("whatsapp_brief"):
                self.fields["brief_whatsapp_enabled"].disabled = True

    def clean_phone_number(self):
        from apps.accounts.phone_utils import is_valid_phone, normalize_phone

        phone = normalize_phone(self.cleaned_data.get("phone_number", ""))
        if phone and not is_valid_phone(phone):
            raise forms.ValidationError("Enter a valid phone number (e.g. 0712345678).")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        from apps.accounts.phone_utils import apply_phone_to_user

        apply_phone_to_user(user, self.cleaned_data.get("phone_number", ""))
        if self.fields["brief_email_enabled"].disabled:
            user.brief_email_enabled = self.instance.brief_email_enabled
        if self.fields["brief_whatsapp_enabled"].disabled:
            user.brief_whatsapp_enabled = self.instance.brief_whatsapp_enabled
        if commit:
            user.save()
        return user


class BrandProfileForm(forms.ModelForm):
    # ── Onboarding Step 2 fields (voice & identity) ──
    TONE_CHOICES = [
        ("confident", "Confident"),
        ("approachable", "Approachable"),
        ("witty", "Witty / Humorous"),
        ("professional", "Professional"),
        ("casual", "Casual / Relaxed"),
        ("bold", "Bold / Provocative"),
        ("educational", "Educational"),
        ("inspirational", "Inspirational"),
        ("empathetic", "Empathetic / Warm"),
        ("authoritative", "Authoritative / Expert"),
        ("playful", "Playful / Fun"),
        ("minimalist", "Minimalist / Direct"),
    ]

    tone_selection = forms.MultipleChoiceField(
        choices=TONE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "rounded text-kova-600"}),
        required=False,
        label="Brand tone (pick 3-5)",
    )

    content_pillars_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "input", "rows": 3, "placeholder": "One topic per line. E.g.:\nProduct updates\nIndustry trends\nCustomer stories"}
        ),
        label="Content pillars",
        help_text="Main topics/themes for your content, one per line.",
    )

    brand_voice_examples_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "input", "rows": 5, "placeholder": "Paste 2-3 posts that represent your brand voice.\nSeparate each example with a blank line."}
        ),
        label="Voice examples",
        help_text="Sample posts that match your brand voice. Separate examples with a blank line (max 5).",
    )

    brand_colors_text = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "#FF5733, #1A1A2E, #FFFFFF",
            }
        ),
        label="Brand colors",
        help_text="Enter hex color codes separated by commas. Used for graphics, carousels, and AI image prompts.",
    )

    # ── Onboarding Step 1 fields (basics) ──
    key_offerings_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "input", "rows": 3, "placeholder": "One product or service per line."}
        ),
        label="Key products / services",
        help_text="What does your business sell or offer? One per line.",
    )

    # ── Onboarding Step 3 fields (goals & CTA) ──
    GOAL_CHOICES = [
        ("grow_followers", "Grow followers"),
        ("drive_traffic", "Drive website traffic"),
        ("generate_leads", "Generate leads"),
        ("build_community", "Build community"),
        ("brand_awareness", "Increase brand awareness"),
        ("thought_leadership", "Establish thought leadership"),
        ("customer_support", "Customer support & engagement"),
    ]

    goals_selection = forms.MultipleChoiceField(
        choices=GOAL_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "rounded text-kova-600"}),
        required=False,
        label="Social media goals",
    )

    autopilot_platforms_selection = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "rounded text-kova-600"}),
        required=False,
        label="Autopilot platforms",
        help_text="Leave empty to use all connected platforms.",
    )

    class Meta:
        model = UserProfile
        fields = [
            "company_name",
            "website_url",
            "industry",
            "industry_other",
            # Geographic / market context (drives holiday awareness)
            "country",
            "city",
            "brand_voice",
            "target_audience",
            "posting_frequency",
            "autopilot_enabled",
            "autopilot_posts_per_week",
            "commerce_autopilot",
            "catalog_showcase_weekly",
            "auto_approve_posts",
            "engage_autonomy_level",
            "content_language",
            "brand_restrictions",
            "visual_style",
            "storefront_vibe",
            "brand_logo_url",
            # CTA fields
            "default_cta_type",
            "default_cta_url",
            "cta_phone",
            "cta_email",
            "cta_whatsapp",
        ]
        widgets = {
            "company_name": forms.TextInput(attrs={"class": "input", "placeholder": "Your company or brand name"}),
            "website_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://example.com"}),
            "industry": forms.Select(attrs={"class": "input", "x-model": "industry", "@change": "industry = $event.target.value"}),
            "industry_other": forms.TextInput(attrs={"class": "input", "placeholder": "Enter your industry", "x-show": "industry === 'other'"}),
            "brand_voice": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 4,
                    "placeholder": "Professional but approachable, uses humor occasionally...",
                }
            ),
            "target_audience": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Marketing managers at mid-size SaaS companies...",
                }
            ),
            "posting_frequency": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 50}),
            "autopilot_posts_per_week": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 14}),
            "content_language": forms.Select(attrs={"class": "input"}),
            "brand_restrictions": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Never mention competitors by name, always include a call-to-action...",
                }
            ),
            "visual_style": forms.Select(attrs={"class": "input"}),
            "storefront_vibe": forms.Select(attrs={"class": "input"}),
            "brand_logo_url": forms.URLInput(
                attrs={"class": "input", "placeholder": "https://yourcdn.com/logo.png"}
            ),
            "default_cta_type": forms.Select(attrs={"class": "input", "x-model": "ctaType"}),
            "default_cta_url": forms.TextInput(attrs={"class": "input", "placeholder": "https://yoursite.com or /k/your-page/"}),
            "cta_phone": forms.TextInput(attrs={"class": "input", "placeholder": "+254712345678"}),
            "cta_email": forms.EmailInput(attrs={"class": "input", "placeholder": "hello@yourbrand.com"}),
            "cta_whatsapp": forms.TextInput(attrs={"class": "input", "placeholder": "254712345678"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            if self.instance.brand_colors:
                self.fields["brand_colors_text"].initial = ", ".join(self.instance.brand_colors)
            if self.instance.content_pillars:
                self.fields["content_pillars_text"].initial = "\n".join(self.instance.content_pillars)
            if self.instance.tone_attributes:
                self.fields["tone_selection"].initial = self.instance.tone_attributes
            if self.instance.brand_voice_examples:
                self.fields["brand_voice_examples_text"].initial = "\n\n".join(self.instance.brand_voice_examples)
            if self.instance.key_offerings:
                self.fields["key_offerings_text"].initial = "\n".join(self.instance.key_offerings)
            if self.instance.goals:
                self.fields["goals_selection"].initial = self.instance.goals
            if self.instance.autopilot_platforms:
                self.fields["autopilot_platforms_selection"].initial = self.instance.autopilot_platforms

        if "storefront_vibe" in self.fields:
            self.fields["storefront_vibe"].label = "Shop page style"

            # ── Plan-tier-gate engage_autonomy_level ─────────────────────
            # Per docs/specs/ENGAGE_AGENT_V2_SPEC.md: Starter caps at
            # SUGGEST, Growth/Pro at GRADUATED, Agency unlocks AGGRESSIVE.
            # We narrow the field's choices to the levels this plan allows
            # so the user can't even see options they cannot select.
            from apps.agents.engage_routing import is_level_allowed
            from apps.accounts.models import UserProfile
            plan = (self.instance.plan or "starter").lower()
            allowed_levels = [
                (val, label) for val, label in UserProfile.EngageAutonomyLevel.choices
                if is_level_allowed(val, plan)
            ]
            self.fields["engage_autonomy_level"].choices = allowed_levels

        from apps.platforms.models import SocialAccount
        self.fields["autopilot_platforms_selection"].choices = SocialAccount.Platform.choices

    def clean_engage_autonomy_level(self):
        """Defence-in-depth: reject levels above the plan's cap.

        The __init__ narrows the dropdown, but a tampered form POST could
        still submit a higher level. Validate server-side.
        """
        from apps.agents.engage_routing import is_level_allowed
        level = (self.cleaned_data.get("engage_autonomy_level") or "suggest").lower()
        plan = (self.instance.plan or "starter").lower() if self.instance else "starter"
        if not is_level_allowed(level, plan):
            from django.forms import ValidationError
            from apps.agents.engage_routing import max_level_for_plan
            raise ValidationError(
                f"Your plan ({plan.title()}) does not allow {level.title()} "
                f"autonomy. Maximum allowed: {max_level_for_plan(plan).title()}."
            )
        return level

    def clean_auto_approve_posts(self):
        from django.forms import ValidationError

        from apps.billing.enforcement import check_auto_approve_plan

        enabled = self.cleaned_data.get("auto_approve_posts")
        if not enabled:
            return False
        user = getattr(self, "user", None)
        if user is None and self.instance:
            user = getattr(self.instance, "user", None)
        if user:
            allowed, msg = check_auto_approve_plan(user)
            if not allowed:
                raise ValidationError(msg)
        return enabled

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Brand colors
        colors_text = self.cleaned_data.get("brand_colors_text", "")
        if colors_text.strip():
            instance.brand_colors = [c.strip() for c in colors_text.split(",") if c.strip()]
        else:
            instance.brand_colors = []
        # Content pillars
        pillars_text = self.cleaned_data.get("content_pillars_text", "")
        instance.content_pillars = [p.strip() for p in pillars_text.split("\n") if p.strip()]
        # Tone attributes
        instance.tone_attributes = self.cleaned_data.get("tone_selection", [])
        # Brand voice examples
        examples_text = self.cleaned_data.get("brand_voice_examples_text", "")
        if examples_text.strip():
            instance.brand_voice_examples = [ex.strip() for ex in examples_text.split("\n\n") if ex.strip()][:5]
        else:
            instance.brand_voice_examples = []
        # Key offerings
        offerings_text = self.cleaned_data.get("key_offerings_text", "")
        instance.key_offerings = [o.strip() for o in offerings_text.split("\n") if o.strip()]
        # Goals
        instance.goals = self.cleaned_data.get("goals_selection", [])
        instance.autopilot_platforms = self.cleaned_data.get("autopilot_platforms_selection", [])
        if commit:
            instance.save()
        return instance


class PhotoroomBrandKitForm(forms.Form):
    """Merchant-facing brand kit for Snap studio polish (P1-2)."""

    SHADOW_CHOICES = [
        ("ai.soft", "Soft shadow"),
        ("ai.hard", "Hard shadow"),
        ("ai.floating", "Floating shadow"),
    ]
    PADDING_CHOICES = [
        ("0.06", "Tight (6%)"),
        ("0.07", "Standard (7%)"),
        ("0.08", "Balanced (8%)"),
        ("0.10", "Comfortable (10%)"),
        ("0.12", "Generous (12%)"),
    ]
    STUDIO_BG_CHOICES = [
        ("brand", "Brand primary color"),
        ("white", "Clean white"),
        ("dark", "Dark premium"),
    ]

    brand_kit_enabled = forms.BooleanField(
        required=False,
        initial=True,
        label="Apply brand kit to Snap polish",
        help_text="Locks shadow, padding, and studio background across every polished scene.",
    )
    shadow_mode = forms.ChoiceField(
        choices=SHADOW_CHOICES,
        initial="ai.soft",
        label="Shadow style",
        widget=forms.Select(attrs={"class": "input"}),
    )
    padding = forms.ChoiceField(
        choices=PADDING_CHOICES,
        initial="0.08",
        label="Product padding",
        widget=forms.Select(attrs={"class": "input"}),
    )
    studio_bg_pref = forms.ChoiceField(
        choices=STUDIO_BG_CHOICES,
        initial="brand",
        label="Studio background",
        widget=forms.Select(attrs={"class": "input"}),
    )
    outline_color = forms.CharField(
        required=False,
        label="Outline / accent color",
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "#FF5733"}),
        help_text="Optional accent for outline variants. Defaults to your secondary brand color.",
    )

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        if profile is not None:
            overrides = getattr(profile, "photoroom_brand_template", None) or {}
            if isinstance(overrides, dict):
                if overrides.get("enabled") is False:
                    self.fields["brand_kit_enabled"].initial = False
                if overrides.get("shadow_mode"):
                    self.fields["shadow_mode"].initial = overrides["shadow_mode"]
                if overrides.get("padding") is not None:
                    pad = str(overrides["padding"])
                    if pad in dict(self.PADDING_CHOICES):
                        self.fields["padding"].initial = pad
                if overrides.get("studio_bg_pref"):
                    pref = overrides["studio_bg_pref"]
                    if pref in dict(self.STUDIO_BG_CHOICES):
                        self.fields["studio_bg_pref"].initial = pref
                if overrides.get("outline_color"):
                    raw = overrides["outline_color"]
                    self.fields["outline_color"].initial = (
                        raw if raw.startswith("#") else f"#{raw}"
                    )

    def clean_outline_color(self):
        raw = (self.cleaned_data.get("outline_color") or "").strip()
        if not raw:
            return ""
        hex_part = raw.lstrip("#").upper()
        if len(hex_part) != 6 or any(c not in "0123456789ABCDEF" for c in hex_part):
            from django.forms import ValidationError

            raise ValidationError("Enter a valid hex color (e.g. #FF5733).")
        return f"#{hex_part}"

    def save(self, profile):
        overrides: dict = {}
        if self.cleaned_data.get("brand_kit_enabled"):
            overrides["enabled"] = True
            overrides["shadow_mode"] = self.cleaned_data["shadow_mode"]
            overrides["padding"] = self.cleaned_data["padding"]
            overrides["studio_bg_pref"] = self.cleaned_data["studio_bg_pref"]
            outline = self.cleaned_data.get("outline_color") or ""
            if outline:
                overrides["outline_color"] = outline.lstrip("#").upper()
        else:
            overrides["enabled"] = False
        profile.photoroom_brand_template = overrides
        profile.save(update_fields=["photoroom_brand_template"])
        return profile


class AutopilotSettingsForm(forms.ModelForm):
    """Operations Autopilot toggles — all default off."""

    class Meta:
        model = UserProfile
        fields = [
            "autopilot_auto_publish_approved",
            "autopilot_auto_enroll_leads",
            "autopilot_auto_create_wa_leads",
            "autopilot_wa_followup_24h",
            "autopilot_wa_faq_replies",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        from apps.accounts.autopilot_helpers import MAX_FAQ_ENTRIES

        for i in range(MAX_FAQ_ENTRIES):
            self.fields[f"faq_keywords_{i}"] = forms.CharField(
                required=False,
                label=f"FAQ keywords {i + 1}",
                widget=forms.TextInput(
                    attrs={
                        "class": "input",
                        "placeholder": "hours, open, location (comma-separated)",
                    }
                ),
            )
            self.fields[f"faq_reply_{i}"] = forms.CharField(
                required=False,
                label=f"FAQ reply {i + 1}",
                widget=forms.Textarea(
                    attrs={"class": "input", "rows": 2, "placeholder": "Auto-reply when keywords match"},
                ),
            )

        if self.instance and self.instance.pk:
            for i, entry in enumerate((self.instance.wa_faq_answers or [])[:MAX_FAQ_ENTRIES]):
                kws = entry.get("keywords") or []
                if isinstance(kws, list):
                    kws = ", ".join(kws)
                self.fields[f"faq_keywords_{i}"].initial = kws
                self.fields[f"faq_reply_{i}"].initial = entry.get("reply", "")

    def clean(self):
        cleaned = super().clean()
        from apps.accounts.autopilot_helpers import whatsapp_autopilot_allowed
        from django.forms import ValidationError

        user = self.user or getattr(self.instance, "user", None)
        wa_fields = (
            "autopilot_auto_create_wa_leads",
            "autopilot_wa_followup_24h",
            "autopilot_wa_faq_replies",
        )
        if user and any(cleaned.get(f) for f in wa_fields):
            if not whatsapp_autopilot_allowed(user):
                raise ValidationError(
                    "WhatsApp follow-up automations require Kazi (Growth) inbox or Biashara (Pro)."
                )
        return cleaned

    def save(self, commit=True):
        from apps.accounts.autopilot_helpers import MAX_FAQ_ENTRIES, normalize_faq_answers

        instance = super().save(commit=False)
        faq_raw = []
        for i in range(MAX_FAQ_ENTRIES):
            keywords = self.cleaned_data.get(f"faq_keywords_{i}", "")
            reply = self.cleaned_data.get(f"faq_reply_{i}", "")
            if keywords or reply:
                faq_raw.append({"keywords": keywords, "reply": reply})
        instance.wa_faq_answers = normalize_faq_answers(faq_raw)
        if commit:
            instance.save()
        return instance


class CTASettingsForm(forms.ModelForm):
    """Default CTA preferences for post generation."""

    class Meta:
        model = UserProfile
        fields = [
            "default_cta_type",
            "default_cta_url",
            "cta_phone",
            "cta_email",
            "cta_whatsapp",
        ]
        widgets = {
            "default_cta_type": forms.Select(attrs={"class": "input", "x-model": "ctaType"}),
            "default_cta_url": forms.TextInput(attrs={"class": "input", "placeholder": "https://yoursite.com or /k/your-page/"}),
            "cta_phone": forms.TextInput(attrs={"class": "input", "placeholder": "+254712345678"}),
            "cta_email": forms.EmailInput(attrs={"class": "input", "placeholder": "hello@yourbrand.com"}),
            "cta_whatsapp": forms.TextInput(attrs={"class": "input", "placeholder": "254712345678"}),
        }


class OnboardingExpressStep1Form(forms.ModelForm):
    """Minimal Step 1 — name, business, industry, optional phone/website."""

    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Your name"}),
    )
    phone_number = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "07XX XXX XXX",
            "autocomplete": "tel",
        }),
        label="Phone",
        help_text="For WhatsApp updates, support, and M-Pesa.",
    )

    class Meta:
        model = UserProfile
        fields = ["company_name", "website_url", "industry", "industry_other"]
        widgets = {
            "company_name": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "Business or brand name",
            }),
            "website_url": forms.URLInput(attrs={
                "class": "input",
                "placeholder": "https://yoursite.com (optional)",
            }),
            "industry": forms.Select(attrs={
                "class": "input",
                "x-model": "industry",
                "@change": "industry = $event.target.value",
            }),
            "industry_other": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "Describe your industry",
                "x-show": "industry === 'other'",
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["company_name"].required = True
        self.fields["industry"].required = True
        if user:
            self.fields["full_name"].initial = user.full_name
            if user.phone_number:
                self.fields["phone_number"].required = False
                self.fields["phone_number"].widget = forms.HiddenInput()
                self.fields["phone_number"].initial = user.phone_number

    def clean_phone_number(self):
        phone = normalize_phone(self.cleaned_data.get("phone_number", ""))
        if not phone and self.user and (self.user.phone_number or "").strip():
            return self.user.phone_number
        if not phone:
            raise forms.ValidationError("Phone number is required.")
        if not is_valid_phone(phone):
            raise forms.ValidationError(
                "Enter a valid phone number (Kenyan 07xx/01xx/02xx or international +country code)."
            )
        return phone

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
            from apps.accounts.industry_packs import apply_pack
            self.applied_pack_fields = apply_pack(profile, profile.industry)
        if self.user:
            self.user.full_name = self.cleaned_data["full_name"]
            if not self.user.timezone:
                self.user.timezone = "Africa/Nairobi"
            if commit:
                self.user.save(update_fields=["full_name", "timezone"])
                apply_phone_to_user(self.user, self.cleaned_data.get("phone_number", ""))
        return profile


class OnboardingStep1Form(forms.ModelForm):
    """About you & brand basics."""

    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Your full name"}),
    )
    timezone = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "input"}),
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "+254712345678 or 07XX XXX XXX",
            "autocomplete": "tel",
        }),
        label="Phone number",
        help_text="Optional — used for WhatsApp CTAs and M-Pesa billing hints.",
    )
    key_offerings_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 3,
                "placeholder": "One product or service per line. E.g.:\nCustom birthday cakes\nCatering services\nBaking masterclasses",
            }
        ),
        label="Key products / services",
        help_text="What does your business sell or offer? One per line.",
    )

    class Meta:
        model = UserProfile
        fields = ["company_name", "website_url", "industry", "industry_other", "content_language"]
        widgets = {
            "company_name": forms.TextInput(attrs={"class": "input", "placeholder": "Your brand name"}),
            "website_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://yoursite.com"}),
            "industry": forms.Select(attrs={"class": "input", "x-model": "industry", "@change": "industry = $event.target.value"}),
            "industry_other": forms.TextInput(attrs={"class": "input", "placeholder": "Enter your industry", "x-show": "industry === 'other'"}),
            "content_language": forms.Select(attrs={"class": "input"}),
        }

    # Common African timezones surfaced first — Kova's primary market.
    AFRICA_TZ_PRIORITY = [
        "Africa/Nairobi",
        "Africa/Kampala",
        "Africa/Dar_es_Salaam",
        "Africa/Kigali",
        "Africa/Lagos",
        "Africa/Accra",
        "Africa/Cairo",
        "Africa/Johannesburg",
        "Africa/Casablanca",
        "Africa/Addis_Ababa",
    ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        import zoneinfo
        all_tz = zoneinfo.available_timezones()
        priority = [tz for tz in self.AFRICA_TZ_PRIORITY if tz in all_tz]
        rest = sorted(all_tz - set(priority))
        self.fields["timezone"].choices = [
            ("Common African timezones", [(tz, tz) for tz in priority]),
            ("All timezones", [(tz, tz) for tz in rest]),
        ]
        if user:
            self.fields["full_name"].initial = user.full_name
            self.fields["timezone"].initial = user.timezone or "Africa/Nairobi"
        if self.instance and self.instance.key_offerings:
            self.fields["key_offerings_text"].initial = "\n".join(self.instance.key_offerings)
        if user and user.phone_number:
            self.fields["phone_number"].initial = user.phone_number

    def clean_phone_number(self):
        phone = normalize_phone(self.cleaned_data.get("phone_number", ""))
        if not phone:
            raise forms.ValidationError("Phone number is required.")
        if not is_valid_phone(phone):
            raise forms.ValidationError(
                "Enter a valid phone number (Kenyan 07xx/01xx/02xx or international +country code)."
            )
        return phone

    def save(self, commit=True):
        profile = super().save(commit=False)
        # Save key_offerings from text
        offerings_text = self.cleaned_data.get("key_offerings_text", "")
        profile.key_offerings = [o.strip() for o in offerings_text.split("\n") if o.strip()]
        if commit:
            profile.save()
            # Industry-aware starter pack — fills tone, pillars, goals, posting
            # cadence, CTA, and visual style with sensible defaults if the user
            # hasn't picked anything yet. Never overwrites user-supplied values.
            from apps.accounts.industry_packs import apply_pack
            self.applied_pack_fields = apply_pack(profile, profile.industry)
        if self.user:
            self.user.full_name = self.cleaned_data["full_name"]
            self.user.timezone = self.cleaned_data["timezone"]
            if commit:
                self.user.save(update_fields=["full_name", "timezone"])
                apply_phone_to_user(self.user, self.cleaned_data.get("phone_number", ""))
        return profile


class OnboardingStep2ReviewForm(forms.ModelForm):
    """Legacy full brand review form — used in Settings, not express onboarding."""
    """Single 'Review your brand' page — combines what used to be Step 2 + Step 3.

    Pre-filled when Magic Fill / URL inference / industry pack populated the
    profile during Step 1. User skims sections (Voice · Visuals · Goals ·
    Agent autonomy · Default CTA) and edits only what's off.
    """

    TONE_CHOICES = [
        ("confident", "Confident"),
        ("approachable", "Approachable"),
        ("witty", "Witty / Humorous"),
        ("professional", "Professional"),
        ("casual", "Casual / Relaxed"),
        ("bold", "Bold / Provocative"),
        ("educational", "Educational"),
        ("inspirational", "Inspirational"),
        ("empathetic", "Empathetic / Warm"),
        ("authoritative", "Authoritative / Expert"),
        ("playful", "Playful / Fun"),
        ("minimalist", "Minimalist / Direct"),
    ]

    GOAL_CHOICES = [
        ("grow_followers", "Grow followers"),
        ("drive_traffic", "Drive website traffic"),
        ("generate_leads", "Generate leads"),
        ("build_community", "Build community"),
        ("brand_awareness", "Increase brand awareness"),
        ("thought_leadership", "Establish thought leadership"),
        ("customer_support", "Customer support & engagement"),
    ]

    # ── Voice / visuals (was Step 2) ────────────────────────────────────────
    tone_selection = forms.MultipleChoiceField(
        choices=TONE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "rounded text-kova-600"}),
        required=False,
        label="Brand tone (pick 3-5)",
        help_text="Tones that best describe how your brand communicates.",
    )
    content_pillars_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "input", "rows": 3,
            "placeholder": "One topic per line. E.g.:\nProduct updates\nIndustry trends\nCustomer stories",
        }),
        help_text="Main content topics/themes, one per line.",
    )
    brand_voice_examples_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "input", "rows": 4,
            "placeholder": "Paste 2-3 posts that represent your brand voice.\nSeparate each example with a blank line.",
        }),
        label="Voice examples (optional)",
        help_text="Sample posts that match your brand voice. Separate examples with a blank line (max 5).",
    )
    brand_colors_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "#FF5733, #1A1A2E, #FFFFFF"}),
        label="Brand colors",
        help_text="Hex codes separated by commas. Used for graphics and AI image prompts.",
    )

    # ── Goals & autonomy (was Step 3) ───────────────────────────────────────
    goals_selection = forms.MultipleChoiceField(
        choices=GOAL_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "rounded text-kova-600"}),
        required=False,
    )
    daily_brief_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"class": "input", "type": "time"}),
        help_text="When should your daily AI brief be compiled? (In your timezone)",
    )

    class Meta:
        model = UserProfile
        fields = [
            # Voice / visuals
            "brand_voice", "target_audience", "brand_restrictions",
            "visual_style",
            # Goals / autonomy
            "posting_frequency", "auto_approve_posts", "engage_autonomy_level",
            "default_cta_type", "default_cta_url", "cta_whatsapp",
        ]
        widgets = {
            "brand_voice": forms.Textarea(attrs={
                "class": "input", "rows": 3,
                "placeholder": "Describe how your brand sounds on social media.",
            }),
            "target_audience": forms.Textarea(attrs={
                "class": "input", "rows": 3,
                "placeholder": "Who are you talking to? Age range, location, interests, pain points.",
            }),
            "brand_restrictions": forms.Textarea(attrs={
                "class": "input", "rows": 2,
                "placeholder": "Topics or words to avoid. E.g.: Never mention competitors by name.",
            }),
            "visual_style": forms.Select(attrs={"class": "input"}),
            "posting_frequency": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 50}),
            "default_cta_type": forms.Select(attrs={"class": "input", "x-model": "ctaType"}),
            "default_cta_url": forms.TextInput(attrs={"class": "input", "placeholder": "https://yoursite.com"}),
            "cta_whatsapp": forms.TextInput(attrs={"class": "input", "placeholder": "254712345678"}),
        }

    # Render in a logical "review" order — voice first, then audience, content,
    # visuals, goals, cadence, autonomy, CTA at the end (collapsible).
    field_order = [
        "brand_voice",
        "target_audience",
        "tone_selection",
        "brand_voice_examples_text",
        "content_pillars_text",
        "brand_restrictions",
        "visual_style",
        "brand_colors_text",
        "goals_selection",
        "posting_frequency",
        "daily_brief_time",
        "auto_approve_posts",
        "engage_autonomy_level",
        "default_cta_type",
        "default_cta_url",
        "cta_whatsapp",
    ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if self.instance:
            if self.instance.content_pillars:
                self.fields["content_pillars_text"].initial = "\n".join(self.instance.content_pillars)
            if self.instance.tone_attributes:
                self.fields["tone_selection"].initial = self.instance.tone_attributes
            if self.instance.brand_voice_examples:
                self.fields["brand_voice_examples_text"].initial = "\n\n".join(self.instance.brand_voice_examples)
            if self.instance.brand_colors:
                self.fields["brand_colors_text"].initial = ", ".join(self.instance.brand_colors)
            if self.instance.goals:
                self.fields["goals_selection"].initial = self.instance.goals
        if user:
            self.fields["daily_brief_time"].initial = user.daily_brief_time

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Pillars
        pillars_text = self.cleaned_data.get("content_pillars_text", "")
        instance.content_pillars = [p.strip() for p in pillars_text.split("\n") if p.strip()]
        # Tones
        instance.tone_attributes = self.cleaned_data.get("tone_selection", [])
        # Voice examples (split on blank lines, cap at 5)
        examples_text = self.cleaned_data.get("brand_voice_examples_text", "")
        if examples_text.strip():
            instance.brand_voice_examples = [
                ex.strip() for ex in examples_text.split("\n\n") if ex.strip()
            ][:5]
        else:
            instance.brand_voice_examples = []
        # Colors
        colors_text = self.cleaned_data.get("brand_colors_text", "")
        if colors_text.strip():
            instance.brand_colors = [c.strip() for c in colors_text.split(",") if c.strip()]
        else:
            instance.brand_colors = []
        # Goals
        instance.goals = self.cleaned_data.get("goals_selection", [])
        if commit:
            instance.save()
        if self.user:
            self.user.daily_brief_time = self.cleaned_data["daily_brief_time"]
            if commit:
                self.user.save(update_fields=["daily_brief_time"])
        return instance
