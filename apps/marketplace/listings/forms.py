from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import Listing, ListingImage, ListingOptionValue, PersonalizationFieldType


class ListingForm(forms.ModelForm):
    quantity_available = forms.IntegerField(
        label=_('Quantity available'),
        min_value=0,
        initial=1,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
    )

    class Meta:
        model = Listing
        fields = [
            'title',
            'category',
            'short_description',
            'description',
            'base_price',
            'sku',
            'product_type',
            'shipping_profile',
            'seo_title',
            'seo_description',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'field-input'}),
            'category': forms.Select(attrs={'class': 'field-select'}),
            'short_description': forms.TextInput(attrs={'class': 'field-input'}),
            'description': forms.Textarea(attrs={'class': 'field-textarea', 'rows': 5}),
            'base_price': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01', 'min': '0.01'}),
            'sku': forms.TextInput(attrs={'class': 'field-input'}),
            'product_type': forms.Select(attrs={'class': 'field-select'}),
            'shipping_profile': forms.Select(attrs={'class': 'field-select'}),
            'seo_title': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Concise search title (optional)'}),
            'seo_description': forms.Textarea(attrs={'class': 'field-textarea', 'rows': 3, 'placeholder': 'Search and social summary (optional)'}),
        }

    def __init__(self, *args, **kwargs):
        shop = kwargs.pop('shop', None)
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(is_visible=True).order_by(
            'position', 'name'
        )
        self.fields['product_type'].required = False
        if shop is None and self.instance and self.instance.pk:
            shop = self.instance.shop
        if shop is not None:
            self.fields['shipping_profile'].queryset = shop.shipping_profiles.filter(is_active=True).order_by('name')
        else:
            self.fields['shipping_profile'].queryset = self.fields['shipping_profile'].queryset.none()
        self.fields['product_type'].initial = 'physical'
        if self.instance and self.instance.pk:
            base = self.instance.inventory_rows.filter(variant__isnull=True).first()
            if base:
                self.fields['quantity_available'].initial = base.quantity_available

    def clean_base_price(self):
        price = self.cleaned_data['base_price']
        if price is None or price < Decimal('0.01'):
            raise forms.ValidationError(_('Enter a valid price of at least 0.01.'))
        return price

    def clean_product_type(self):
        return self.cleaned_data.get('product_type') or 'physical'


class InventoryForm(forms.Form):
    quantity_available = forms.IntegerField(
        label=_('Quantity available'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
    )
    low_stock_threshold = forms.IntegerField(
        label=_('Low stock threshold'),
        min_value=0,
        initial=3,
        widget=forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
    )


class ListingImageForm(forms.Form):
    image = forms.ImageField(label=_('Image'))
    alt_text = forms.CharField(
        label=_('Alt text'),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'field-input'}),
    )


class DigitalAssetForm(forms.Form):
    title = forms.CharField(max_length=160, widget=forms.TextInput(attrs={'class': 'field-input'}))
    file = forms.FileField()
    version = forms.CharField(max_length=40, required=False, widget=forms.TextInput(attrs={'class': 'field-input'}))


class ListingVariantForm(forms.Form):
    name = forms.CharField(
        label=_('Variant name'),
        max_length=120,
        widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'e.g. Large / Red'}),
    )
    sku = forms.CharField(
        label=_('SKU'),
        max_length=64,
        required=False,
        widget=forms.TextInput(attrs={'class': 'field-input'}),
    )
    price_override = forms.DecimalField(
        label=_('Price override (optional)'),
        required=False,
        min_value=Decimal('0.01'),
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
    )
    quantity_available = forms.IntegerField(
        label=_('Quantity'),
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
    )
    option_values = forms.ModelMultipleChoiceField(
        queryset=ListingOptionValue.objects.none(), required=False,
        widget=forms.SelectMultiple(attrs={'class': 'field-select', 'size': 6}),
        help_text=_('Choose at most one value from each option group.'),
    )
    cover_image = forms.ModelChoiceField(
        queryset=ListingImage.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'field-select'}),
    )

    def __init__(self, *args, listing=None, **kwargs):
        super().__init__(*args, **kwargs)
        if listing is not None:
            self.fields['option_values'].queryset = ListingOptionValue.objects.filter(option__listing=listing).select_related('option')
            self.fields['option_values'].label_from_instance = lambda value: f'{value.option.name}: {value.value}'
            self.fields['cover_image'].queryset = listing.images.all()


class ListingOptionForm(forms.Form):
    name = forms.CharField(max_length=80, widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Size'}))
    values = forms.CharField(widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Small, Medium, Large'}))


class PersonalizationFieldForm(forms.Form):
    label = forms.CharField(max_length=120, widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Name to engrave'}))
    instructions = forms.CharField(max_length=300, required=False, widget=forms.TextInput(attrs={'class': 'field-input'}))
    field_type = forms.ChoiceField(choices=PersonalizationFieldType.choices, widget=forms.Select(attrs={'class': 'field-select'}))
    options = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Option A, Option B'}))
    is_required = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'field-checkbox'}))
    max_length = forms.IntegerField(min_value=1, max_value=500, initial=120, widget=forms.NumberInput(attrs={'class': 'field-input'}))


class ListingAttributeForm(forms.Form):
    name = forms.CharField(
        label=_('Attribute'),
        max_length=80,
        widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Material'}),
    )
    value = forms.CharField(
        label=_('Value'),
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Sisal'}),
    )
