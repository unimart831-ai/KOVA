from django import forms

from apps.content.models import ContentSeed, Post


class ContentSeedForm(forms.ModelForm):
    """Form for dropping a content idea."""

    class Meta:
        model = ContentSeed
        fields = ["idea", "notes", "target_platforms"]
        widgets = {
            "idea": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Drop your idea here... e.g. 'AI is changing how small businesses do marketing'",
                "class": "input",
            }),
            "notes": forms.Textarea(attrs={
                "rows": 2,
                "placeholder": "Any extra context or instructions for the AI (optional)",
                "class": "input",
            }),
            "target_platforms": forms.HiddenInput(),
        }

    def clean_target_platforms(self):
        val = self.cleaned_data.get("target_platforms")
        if isinstance(val, str):
            import json
            try:
                val = json.loads(val) if val else []
            except json.JSONDecodeError:
                val = []
        return val or []


class PostEditForm(forms.ModelForm):
    """Form for editing a generated post before approval."""

    class Meta:
        model = Post
        fields = ["content_text"]
        widgets = {
            "content_text": forms.Textarea(attrs={
                "rows": 8,
                "class": "input",
            }),
        }
