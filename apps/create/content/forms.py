from django import forms

from apps.create.content.models import ContentSeed, MarketingCampaign, Post

OBJECTIVE_IDEA_DEFAULTS = {
    MarketingCampaign.Objective.SALES: (
        "Drive sales this week — highlight our best offer and make it easy to buy."
    ),
    MarketingCampaign.Objective.LEADS: (
        "Generate new leads — invite people to enquire and start a conversation."
    ),
    MarketingCampaign.Objective.AWARENESS: (
        "Grow awareness — introduce the business and why customers choose us."
    ),
    MarketingCampaign.Objective.BOOKINGS: (
        "Get more bookings — push people to reserve a slot this week."
    ),
}


class ContentSeedForm(forms.ModelForm):
    """Goal-first campaign form — objective is primary; idea can be auto-filled."""

    objective = forms.ChoiceField(
        choices=MarketingCampaign.Objective.choices,
        initial=MarketingCampaign.Objective.SALES,
        required=True,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )

    class Meta:
        model = ContentSeed
        fields = ["idea", "notes", "target_platforms", "generate_images"]
        widgets = {
            "idea": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Optional details — offer, product, audience, or angle…",
                "class": "input",
            }),
            "notes": forms.Textarea(attrs={
                "rows": 2,
                "placeholder": "Any extra context or instructions for the AI (optional)",
                "class": "input",
            }),
            "target_platforms": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["idea"].required = False

    def clean_target_platforms(self):
        val = self.cleaned_data.get("target_platforms")
        if isinstance(val, str):
            import json
            try:
                val = json.loads(val) if val else []
            except json.JSONDecodeError:
                val = []
        return val or []

    def clean(self):
        cleaned = super().clean()
        idea = (cleaned.get("idea") or "").strip()
        objective = cleaned.get("objective") or MarketingCampaign.Objective.SALES
        if not idea:
            cleaned["idea"] = OBJECTIVE_IDEA_DEFAULTS.get(
                objective,
                OBJECTIVE_IDEA_DEFAULTS[MarketingCampaign.Objective.SALES],
            )
        return cleaned


class PostEditForm(forms.ModelForm):
    """Form for editing a generated post before approval."""

    class Meta:
        model = Post
        fields = ["content_text", "cta_type", "cta_text", "cta_url", "first_comment"]
        widgets = {
            "content_text": forms.Textarea(attrs={
                "rows": 8,
                "class": "input",
            }),
            "cta_type": forms.Select(attrs={
                "class": "input",
                "x-model": "ctaType",
            }),
            "cta_text": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. Book a free consultation →",
            }),
            "cta_url": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "https://… or phone/email/WhatsApp",
            }),
            "first_comment": forms.Textarea(attrs={
                "rows": 3,
                "class": "input",
                "placeholder": "First comment content (LinkedIn: put CTA link here)",
            }),
        }
