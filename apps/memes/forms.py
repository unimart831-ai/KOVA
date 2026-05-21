from django import forms

from apps.memes.models import MemePreferences, TrendingMeme
from apps.platforms.models import SocialAccount


class MemePreferencesForm(forms.ModelForm):
    preferred_categories_selection = forms.MultipleChoiceField(
        choices=TrendingMeme.Category.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Preferred categories",
    )
    excluded_categories_selection = forms.MultipleChoiceField(
        choices=TrendingMeme.Category.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Excluded categories",
    )
    preferred_humor_selection = forms.MultipleChoiceField(
        choices=TrendingMeme.HumorType.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Preferred humor types",
    )
    preferred_platforms_selection = forms.MultipleChoiceField(
        choices=SocialAccount.Platform.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Preferred platforms",
    )

    class Meta:
        model = MemePreferences
        fields = [
            "is_active",
            "risk_tolerance",
            "max_memes_per_week",
            "auto_queue",
        ]
        widgets = {
            "risk_tolerance": forms.Select(attrs={"class": "input w-full"}),
            "max_memes_per_week": forms.NumberInput(attrs={"class": "input w-full", "min": 1, "max": 20}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            if self.instance.preferred_categories:
                self.fields["preferred_categories_selection"].initial = self.instance.preferred_categories
            if self.instance.excluded_categories:
                self.fields["excluded_categories_selection"].initial = self.instance.excluded_categories
            if self.instance.preferred_humor_types:
                self.fields["preferred_humor_selection"].initial = self.instance.preferred_humor_types
            if self.instance.preferred_platforms:
                self.fields["preferred_platforms_selection"].initial = self.instance.preferred_platforms

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.preferred_categories = self.cleaned_data.get("preferred_categories_selection", [])
        instance.excluded_categories = self.cleaned_data.get("excluded_categories_selection", [])
        instance.preferred_humor_types = self.cleaned_data.get("preferred_humor_selection", [])
        instance.preferred_platforms = self.cleaned_data.get("preferred_platforms_selection", [])
        if commit:
            instance.save()
        return instance
