import re

from django import forms

from apps.accounts.models import User, UserProfile


class KovaSignupForm(forms.Form):
    """Extra fields collected during signup. allauth calls signup() after user creation."""

    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "07XX XXX XXX",
            "autocomplete": "tel",
        }),
        label="Phone number",
        help_text="Kenyan format: 07xx, 01xx, or 02xx",
    )

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()
        if not phone:
            return ""
        # Strip spaces and dashes
        phone = re.sub(r"[\s\-]", "", phone)
        # Must match Kenyan local format: 07xx, 01xx, 02xx (10 digits)
        if not re.match(r"^0[127]\d{8}$", phone):
            raise forms.ValidationError(
                "Enter a valid Kenyan phone number starting with 07, 01, or 02 (10 digits)."
            )
        return phone

    def signup(self, request, user):
        phone = self.cleaned_data.get("phone_number", "")
        if phone:
            user.phone_number = phone
            user.save(update_fields=["phone_number"])


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "timezone", "daily_brief_time", "avatar"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "input", "placeholder": "Your full name"}),
            "timezone": forms.Select(attrs={"class": "input"}),
            "daily_brief_time": forms.TimeInput(attrs={"class": "input", "type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import zoneinfo

        self.fields["timezone"].widget.choices = [(tz, tz) for tz in sorted(zoneinfo.available_timezones())]


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

    class Meta:
        model = UserProfile
        fields = [
            "company_name",
            "website_url",
            "industry",
            "industry_other",
            "brand_voice",
            "target_audience",
            "posting_frequency",
            "auto_approve_posts",
            "auto_engage",
            "content_language",
            "brand_restrictions",
            "visual_style",
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
            "content_language": forms.Select(attrs={"class": "input"}),
            "brand_restrictions": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Never mention competitors by name, always include a call-to-action...",
                }
            ),
            "visual_style": forms.Select(attrs={"class": "input"}),
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


class OnboardingStep1Form(forms.ModelForm):
    """About you & brand basics."""

    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Your full name"}),
    )
    timezone = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "input"}),
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        import zoneinfo
        tz_list = sorted(zoneinfo.available_timezones())
        self.fields["timezone"].choices = [(tz, tz) for tz in tz_list]
        if user:
            self.fields["full_name"].initial = user.full_name
            self.fields["timezone"].initial = user.timezone or "UTC"
        if self.instance and self.instance.key_offerings:
            self.fields["key_offerings_text"].initial = "\n".join(self.instance.key_offerings)

    def save(self, commit=True):
        profile = super().save(commit=False)
        # Save key_offerings from text
        offerings_text = self.cleaned_data.get("key_offerings_text", "")
        profile.key_offerings = [o.strip() for o in offerings_text.split("\n") if o.strip()]
        if commit:
            profile.save()
        if self.user:
            self.user.full_name = self.cleaned_data["full_name"]
            self.user.timezone = self.cleaned_data["timezone"]
            if commit:
                self.user.save(update_fields=["full_name", "timezone"])
        return profile


class OnboardingStep2Form(forms.ModelForm):
    """Brand voice & audience — with guided tone selection and examples."""

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

    brand_colors_text = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "#FF5733, #1A1A2E, #FFFFFF",
            }
        ),
        label="Brand colors",
        help_text="Pick your brand colors — used for graphics, carousels, and AI image styling.",
    )

    class Meta:
        model = UserProfile
        fields = ["brand_voice", "target_audience", "content_pillars", "brand_restrictions", "visual_style"]
        widgets = {
            "brand_voice": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 4,
                    "placeholder": "Describe how your brand sounds on social media.\n\nE.g.: 'We sound like a smart friend who happens to be an expert — confident but never arrogant, uses data and real examples, occasionally drops humor, always ends with something actionable.'",
                }
            ),
            "target_audience": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Be specific! Not just 'young professionals' but:\n'Female entrepreneurs aged 25-40 in Nairobi, running service businesses, active on Instagram/LinkedIn, budget-conscious but willing to pay for time-saving tools.'",
                }
            ),
            "brand_restrictions": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Topics or words to avoid. E.g.:\nNever mention competitors by name\nDon't use slang or abbreviations\nAvoid political topics\nAlways include a call-to-action",
                }
            ),
        }

    tone_selection = forms.MultipleChoiceField(
        choices=TONE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "rounded text-kova-600"}),
        required=False,
        label="Brand tone (pick 3-5)",
        help_text="Select the tones that best describe how your brand communicates.",
    )

    content_pillars_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 3,
                "placeholder": "One topic per line. E.g.:\nProduct updates\nIndustry trends\nCustomer stories",
            }
        ),
        help_text="Enter your main content topics/themes, one per line.",
    )

    brand_voice_examples_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "input",
                "rows": 5,
                "placeholder": "Paste 2-3 posts that represent your brand voice well.\nSeparate each example with a blank line.\n\nE.g.:\nWe just shipped our biggest feature yet. 6 months of work, 47 user interviews, and one obsession: make scheduling actually intelligent. Here's what we built →\n\nEvery morning I wake up to a Daily Brief from our AI. Trending topics, ready-to-approve posts, optimal times calculated. My entire social media takes 5 minutes. That's the future of content.",
            }
        ),
        label="Voice examples (optional but powerful)",
        help_text="Paste your best posts or content that sounds like your brand. Separate examples with a blank line.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.content_pillars:
            self.fields["content_pillars_text"].initial = "\n".join(self.instance.content_pillars)
        if self.instance and self.instance.tone_attributes:
            self.fields["tone_selection"].initial = self.instance.tone_attributes
        if self.instance and self.instance.brand_voice_examples:
            self.fields["brand_voice_examples_text"].initial = "\n\n".join(self.instance.brand_voice_examples)
        if self.instance and self.instance.brand_colors:
            self.fields["brand_colors_text"].initial = ", ".join(self.instance.brand_colors)
        # Hide the JSON fields — we use text proxies
        self.fields.pop("content_pillars")

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Content pillars
        pillars_text = self.cleaned_data.get("content_pillars_text", "")
        instance.content_pillars = [p.strip() for p in pillars_text.split("\n") if p.strip()]
        # Tone attributes
        instance.tone_attributes = self.cleaned_data.get("tone_selection", [])
        # Brand voice examples — split on double newlines
        examples_text = self.cleaned_data.get("brand_voice_examples_text", "")
        if examples_text.strip():
            # Split on blank lines, keep max 5
            examples = [ex.strip() for ex in examples_text.split("\n\n") if ex.strip()]
            instance.brand_voice_examples = examples[:5]
        else:
            instance.brand_voice_examples = []
        # Brand colors
        colors_text = self.cleaned_data.get("brand_colors_text", "")
        if colors_text.strip():
            instance.brand_colors = [c.strip() for c in colors_text.split(",") if c.strip()]
        else:
            instance.brand_colors = []
        if commit:
            instance.save()
        return instance


class OnboardingStep3Form(forms.ModelForm):
    """Goals & preferences."""

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
    )

    daily_brief_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"class": "input", "type": "time"}),
        help_text="When should your daily AI brief be compiled? (In your timezone)",
    )

    class Meta:
        model = UserProfile
        fields = [
            "posting_frequency", "auto_approve_posts", "auto_engage",
            "default_cta_type", "default_cta_url", "cta_whatsapp",
        ]
        widgets = {
            "posting_frequency": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 50}),
            "default_cta_type": forms.Select(attrs={"class": "input", "x-model": "ctaType"}),
            "default_cta_url": forms.TextInput(attrs={"class": "input", "placeholder": "https://yoursite.com"}),
            "cta_whatsapp": forms.TextInput(attrs={"class": "input", "placeholder": "254712345678"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields["daily_brief_time"].initial = user.daily_brief_time
        if self.instance and self.instance.goals:
            self.fields["goals_selection"].initial = self.instance.goals

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.goals = self.cleaned_data.get("goals_selection", [])
        if commit:
            instance.save()
        if self.user:
            self.user.daily_brief_time = self.cleaned_data["daily_brief_time"]
            if commit:
                self.user.save(update_fields=["daily_brief_time"])
        return instance
