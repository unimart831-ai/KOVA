from django import forms

from apps.commerce.leads.models import Lead


class LeadForm(forms.ModelForm):
    """Manual lead creation / edit form."""

    class Meta:
        model = Lead
        fields = ["name", "email", "phone", "source_type", "source_platform", "status", "priority", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Full name"}),
            "email": forms.EmailInput(attrs={"class": "input", "placeholder": "email@example.com"}),
            "phone": forms.TextInput(attrs={"class": "input", "placeholder": "+254712345678"}),
            "source_type": forms.Select(attrs={"class": "input"}),
            "source_platform": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. instagram"}),
            "status": forms.Select(attrs={"class": "input"}),
            "priority": forms.Select(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3, "placeholder": "Notes about this lead…"}),
        }


class LeadNoteForm(forms.Form):
    """Quick note on a lead."""
    note = forms.CharField(
        widget=forms.Textarea(attrs={"class": "input", "rows": 2, "placeholder": "Add a note…"}),
    )


class LeadTagForm(forms.Form):
    """Add a tag to a lead."""
    tag = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Tag name"}),
    )
