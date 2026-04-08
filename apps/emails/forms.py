from django import forms

from apps.emails.models import EmailCampaign, EmailList, EmailSubscriber


class EmailSubscriberForm(forms.ModelForm):
    class Meta:
        model = EmailSubscriber
        fields = ["name", "email", "source"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Subscriber name"}),
            "email": forms.EmailInput(attrs={"class": "input", "placeholder": "email@example.com"}),
            "source": forms.Select(attrs={"class": "input"}),
        }


class EmailListForm(forms.ModelForm):
    class Meta:
        model = EmailList
        fields = ["name", "description", "is_smart"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Newsletter subscribers"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 2, "placeholder": "What is this list for?"}),
            "is_smart": forms.CheckboxInput(),
        }


class EmailCampaignForm(forms.ModelForm):
    class Meta:
        model = EmailCampaign
        fields = [
            "name", "subject", "preview_text", "html_content", "text_content",
            "from_name", "reply_to", "target_list",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Campaign name (internal)"}),
            "subject": forms.TextInput(attrs={"class": "input", "placeholder": "Your email subject line"}),
            "preview_text": forms.TextInput(attrs={"class": "input", "placeholder": "Preview text shown in inbox"}),
            "html_content": forms.Textarea(attrs={"class": "input font-mono text-sm", "rows": 15, "placeholder": "Email HTML content…"}),
            "text_content": forms.Textarea(attrs={"class": "input", "rows": 6, "placeholder": "Plain text fallback"}),
            "from_name": forms.TextInput(attrs={"class": "input", "placeholder": "Your Brand Name"}),
            "reply_to": forms.EmailInput(attrs={"class": "input", "placeholder": "reply@yourbrand.com"}),
            "target_list": forms.Select(attrs={"class": "input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["target_list"].queryset = EmailList.objects.filter(user=user)
