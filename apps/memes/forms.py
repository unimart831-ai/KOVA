from django import forms

from .models import MemePreferences


class MemePreferencesForm(forms.ModelForm):
    class Meta:
        model = MemePreferences
        fields = [
            "is_active",
            "risk_tolerance",
            "preferred_categories",
            "excluded_categories",
            "preferred_humor_types",
            "max_memes_per_week",
            "auto_queue",
            "preferred_platforms",
        ]
        widgets = {
            "risk_tolerance": forms.Select(attrs={"class": "form-select"}),
            "max_memes_per_week": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 20}),
        }
