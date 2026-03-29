from django import forms

from apps.accounts.models import User, UserProfile


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
    class Meta:
        model = UserProfile
        fields = [
            "company_name",
            "website_url",
            "industry",
            "brand_voice",
            "target_audience",
            "posting_frequency",
            "auto_approve_posts",
            "auto_engage",
        ]
        widgets = {
            "company_name": forms.TextInput(attrs={"class": "input", "placeholder": "Your company or brand name"}),
            "website_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://example.com"}),
            "industry": forms.Select(attrs={"class": "input"}),
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
        }


class OnboardingStep1Form(forms.ModelForm):
    """Brand basics."""

    class Meta:
        model = UserProfile
        fields = ["company_name", "website_url", "industry"]
        widgets = {
            "company_name": forms.TextInput(attrs={"class": "input", "placeholder": "Your brand name"}),
            "website_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://yoursite.com"}),
            "industry": forms.Select(attrs={"class": "input"}),
        }


class OnboardingStep2Form(forms.ModelForm):
    """Brand voice & audience."""

    class Meta:
        model = UserProfile
        fields = ["brand_voice", "target_audience", "content_pillars"]
        widgets = {
            "brand_voice": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 4,
                    "placeholder": "Describe how your brand sounds on social media...",
                }
            ),
            "target_audience": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Who are you trying to reach?",
                }
            ),
        }

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.content_pillars:
            self.fields["content_pillars_text"].initial = "\n".join(self.instance.content_pillars)
        # Hide the JSON field
        self.fields.pop("content_pillars")

    def save(self, commit=True):
        instance = super().save(commit=False)
        pillars_text = self.cleaned_data.get("content_pillars_text", "")
        instance.content_pillars = [p.strip() for p in pillars_text.split("\n") if p.strip()]
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

    class Meta:
        model = UserProfile
        fields = ["posting_frequency", "auto_approve_posts"]
        widgets = {
            "posting_frequency": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 50}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.goals:
            self.fields["goals_selection"].initial = self.instance.goals

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.goals = self.cleaned_data.get("goals_selection", [])
        if commit:
            instance.save()
        return instance
