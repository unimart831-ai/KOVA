from django import forms

from apps.campaigns.models import Campaign


class CampaignForm(forms.ModelForm):
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "input"}),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "input"}),
    )

    class Meta:
        model = Campaign
        fields = [
            "name", "description", "objective", "target_platforms",
            "target_audience", "start_date", "end_date", "tags",
            "goal_metric", "goal_target",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Campaign name"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 3, "placeholder": "Describe the campaign goal and strategy"}),
            "objective": forms.Select(attrs={"class": "input"}),
            "target_audience": forms.Textarea(attrs={"class": "input", "rows": 2, "placeholder": "e.g. Small business owners in Kenya aged 25-40"}),
            "goal_metric": forms.Select(attrs={"class": "input"}),
            "goal_target": forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 50", "step": "1"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("End date must be after start date.")
        return cleaned
