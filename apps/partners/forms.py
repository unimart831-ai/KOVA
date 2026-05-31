from django import forms

from .models import PartnerApplication


class MarketplaceVendorJoinForm(forms.Form):
    """Self-serve signup for marketplace vendors (e.g. UNIMART USK sellers)."""

    external_seller_id = forms.CharField(
        max_length=255,
        label="Seller ID (USK)",
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            "placeholder": "USK-00123",
        }),
    )
    full_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            "placeholder": "Jane Kamau",
        }),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            "placeholder": "you@campus.edu",
        }),
    )
    business_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            "placeholder": "Jane Electronics",
        }),
    )
    business_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
            "placeholder": "https://unimartafrica.com/stores/your-shop (optional)",
        }),
    )


class PartnerApplicationForm(forms.ModelForm):
    class Meta:
        model = PartnerApplication
        fields = [
            "full_name",
            "email",
            "phone",
            "company",
            "website",
            "audience_description",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                    "placeholder": "Your full name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                    "placeholder": "you@company.com",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                    "placeholder": "+254 7XX XXX XXX (optional)",
                }
            ),
            "company": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                    "placeholder": "Your company or brand (optional)",
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                    "placeholder": "https://yoursite.com (optional)",
                }
            ),
            "audience_description": forms.Textarea(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:ring-kova-500 focus:border-kova-500",
                    "rows": 4,
                    "placeholder": "Tell us about your audience, channels, and how you plan to share Kova...",
                }
            ),
        }
