from django import forms

from apps.products.models import Product, ProductCategory


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "offering_type", "name", "description", "category", "price", "currency",
            "price_range_min", "price_range_max", "image",
            "product_url", "external_id",
            "stock_status", "quantity", "low_stock_threshold",
            "is_featured", "is_active",
        ]
        widgets = {
            "offering_type": forms.Select(attrs={"class": "input", "x-model": "offeringType"}),
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Website Development, Running Shoes, Social Media Kit"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 3, "placeholder": "Brief description (optional)"}),
            "category": forms.Select(attrs={"class": "input"}),
            "price": forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 5000", "step": "0.01"}),
            "currency": forms.TextInput(attrs={"class": "input w-20", "placeholder": "KES"}),
            "price_range_min": forms.NumberInput(attrs={"class": "input", "placeholder": "Min", "step": "0.01"}),
            "price_range_max": forms.NumberInput(attrs={"class": "input", "placeholder": "Max", "step": "0.01"}),
            "product_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://yourstore.com/product/timberland-casuals"}),
            "external_id": forms.TextInput(attrs={"class": "input", "placeholder": "SKU or external platform ID (optional)"}),
            "stock_status": forms.Select(attrs={"class": "input"}),
            "quantity": forms.NumberInput(attrs={"class": "input", "placeholder": "Optional — exact count"}),
            "low_stock_threshold": forms.NumberInput(attrs={"class": "input", "placeholder": "5"}),
        }

    def __init__(self, *args, user=None, plan_ctx=None, **kwargs):
        super().__init__(*args, **kwargs)
        plan_ctx = plan_ctx or {}
        if user:
            self.fields["category"].queryset = ProductCategory.objects.filter(user=user, is_active=True)
        if not plan_ctx.get("quantity_tracking", True):
            for field in ("quantity", "low_stock_threshold"):
                if field in self.fields:
                    self.fields[field].widget = forms.HiddenInput()
                    self.fields[field].required = False


class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Category name"}),
            "description": forms.TextInput(attrs={"class": "input", "placeholder": "Optional description"}),
        }


class BulkImportForm(forms.Form):
    csv_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "input", "accept": ".csv"}),
    )
    bulk_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "input",
            "rows": 8,
            "placeholder": "Paste products — one per line:\nBlue Sneakers, 5000, in_stock\nRed Sneakers, 4500, out_of_stock",
        }),
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("csv_file") and not cleaned.get("bulk_text"):
            raise forms.ValidationError("Provide either a CSV file or paste product data.")
        return cleaned
