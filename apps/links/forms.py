from django import forms

from apps.links.models import KovaForm, KovaLink, KovaPage


class KovaPageForm(forms.ModelForm):
    class Meta:
        model = KovaPage
        fields = [
            "title", "slug", "bio", "avatar_url",
            "theme", "background_color", "text_color", "accent_color",
            "seo_title", "seo_description", "og_image_url",
            "is_published",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "My Brand",
            }),
            "slug": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "my-brand",
            }),
            "bio": forms.Textarea(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "rows": 3,
                "placeholder": "A short description of you or your brand...",
            }),
            "avatar_url": forms.URLInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "https://...",
            }),
            "theme": forms.Select(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            }),
            "background_color": forms.TextInput(attrs={
                "type": "color",
                "class": "h-10 w-20 rounded border-gray-300 dark:border-gray-600 cursor-pointer",
            }),
            "text_color": forms.TextInput(attrs={
                "type": "color",
                "class": "h-10 w-20 rounded border-gray-300 dark:border-gray-600 cursor-pointer",
            }),
            "accent_color": forms.TextInput(attrs={
                "type": "color",
                "class": "h-10 w-20 rounded border-gray-300 dark:border-gray-600 cursor-pointer",
            }),
            "seo_title": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "SEO title (optional)",
            }),
            "seo_description": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "SEO description (optional)",
            }),
            "og_image_url": forms.URLInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "https://... (social share image)",
            }),
        }


class KovaLinkForm(forms.ModelForm):
    class Meta:
        model = KovaLink
        fields = ["title", "link_type", "url", "icon", "thumbnail_url", "is_featured", "is_active", "order"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "Link title",
            }),
            "link_type": forms.Select(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            }),
            "url": forms.URLInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "https://...",
            }),
            "icon": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "instagram, youtube, globe...",
            }),
            "thumbnail_url": forms.URLInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            }),
            "order": forms.NumberInput(attrs={
                "class": "w-20 rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "min": 0,
            }),
        }


class KovaFormForm(forms.ModelForm):
    """Form for creating/editing a KovaForm (the lead capture form on a page)."""

    class Meta:
        model = KovaForm
        fields = [
            "form_type", "title", "description", "button_text", "success_message",
            "show_name_field", "show_phone_field", "show_message_field",
            "notify_on_submission", "notification_email", "is_active",
        ]
        widgets = {
            "form_type": forms.Select(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            }),
            "title": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            }),
            "description": forms.Textarea(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "rows": 2,
            }),
            "button_text": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            }),
            "success_message": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            }),
            "notification_email": forms.EmailInput(attrs={
                "class": "w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                "placeholder": "Override email (optional)",
            }),
        }


class PublicFormSubmissionForm(forms.Form):
    """The form visitors see on the public Kova page."""

    name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-lg border-gray-300 focus:ring-kova-500 focus:border-kova-500",
            "placeholder": "Your name",
        }),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "w-full rounded-lg border-gray-300 focus:ring-kova-500 focus:border-kova-500",
            "placeholder": "your@email.com",
        }),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-lg border-gray-300 focus:ring-kova-500 focus:border-kova-500",
            "placeholder": "+254...",
        }),
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "w-full rounded-lg border-gray-300 focus:ring-kova-500 focus:border-kova-500",
            "rows": 3,
            "placeholder": "Your message...",
        }),
    )
