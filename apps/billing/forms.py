from django import forms

from apps.billing.models import AgencySalesInquiry

_INPUT = (
    "w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 "
    "bg-white dark:bg-gray-800 text-gray-900 dark:text-white "
    "focus:ring-2 focus:ring-kova-500 focus:border-kova-500"
)
_TEXTAREA = _INPUT + " resize-none"


class AgencySalesInquiryForm(forms.ModelForm):
    class Meta:
        model = AgencySalesInquiry
        fields = [
            "name",
            "email",
            "phone",
            "company_name",
            "message",
            "client_count",
            "plan_interest",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"class": _INPUT, "placeholder": "you@agency.com"}),
            "phone": forms.TextInput(attrs={"class": _INPUT, "placeholder": "+254… (optional)"}),
            "company_name": forms.TextInput(attrs={
                "class": _INPUT,
                "placeholder": "Agency or company name",
            }),
            "message": forms.Textarea(attrs={
                "class": _TEXTAREA,
                "rows": 4,
                "placeholder": "Tell us about your agency, clients, and what you need from Kova…",
            }),
            "client_count": forms.NumberInput(attrs={
                "class": _INPUT,
                "placeholder": "e.g. 12",
                "min": 0,
            }),
            "plan_interest": forms.Select(attrs={"class": _INPUT}),
        }
        labels = {
            "company_name": "Company / agency name",
            "message": "About your agency",
            "client_count": "Number of clients (optional)",
            "plan_interest": "Current plan interest (optional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].required = False
        self.fields["company_name"].required = False
        self.fields["client_count"].required = False
        self.fields["plan_interest"].required = False
        self.fields["plan_interest"].choices = [
            ("", "— Select —"),
            ("agency", "Agency / Wakala"),
            ("pro", "Pro"),
            ("growth", "Growth"),
            ("starter", "Starter"),
            ("not_sure", "Not sure yet"),
        ]
