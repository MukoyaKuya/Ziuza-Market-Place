from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.constants import KENYA_COUNTIES
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.shops.models import Shop


class CreateShopForm(forms.Form):
    name = forms.CharField(
        label=_('Shop name'),
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'field-input',
            'placeholder': 'e.g. Nairobi Craftsmen',
        }),
    )
    description = forms.CharField(
        label=_('About your shop'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'field-textarea',
            'rows': 4,
            'placeholder': 'Tell buyers about your craft, materials, and story…',
        }),
    )
    county = forms.ChoiceField(
        label=_('County'),
        choices=KENYA_COUNTIES,
        initial='Nairobi',
        widget=forms.Select(attrs={'class': 'field-select'}),
    )
    location_text = forms.CharField(
        label=_('Location details'),
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'field-input',
            'placeholder': 'Neighbourhood or town (optional)',
        }),
    )


class ShopSettingsForm(forms.ModelForm):
    county = forms.ChoiceField(
        choices=KENYA_COUNTIES,
        widget=forms.Select(attrs={'class': 'field-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['processing_days_min'].required = False
        self.fields['processing_days_max'].required = False

    class Meta:
        model = Shop
        fields = [
            'name',
            'description',
            'county',
            'location_text',
            'policies',
            'shipping_policy',
            'return_policy',
            'processing_days_min',
            'processing_days_max',
            'vacation_mode',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'field-input'}),
            'description': forms.Textarea(attrs={'class': 'field-textarea', 'rows': 4}),
            'location_text': forms.TextInput(attrs={'class': 'field-input'}),
            'policies': forms.Textarea(attrs={
                'class': 'field-textarea',
                'rows': 4,
                'placeholder': 'Returns, shipping notes, custom orders…',
            }),
            'shipping_policy': forms.Textarea(attrs={'class': 'field-textarea', 'rows': 3, 'placeholder': 'Dispatch, delivery areas, pickup and tracking…'}),
            'return_policy': forms.Textarea(attrs={'class': 'field-textarea', 'rows': 3, 'placeholder': 'Return window, item condition and exclusions…'}),
            'processing_days_min': forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
            'processing_days_max': forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
            'vacation_mode': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
        }
        labels = {
            'vacation_mode': _('Vacation mode (pause sales)'),
            'is_active': _('Shop is active'),
            'policies': _('Shop policies'),
            'location_text': _('Location details'),
        }

    def clean(self):
        cleaned = super().clean()
        minimum = cleaned.get('processing_days_min')
        maximum = cleaned.get('processing_days_max')
        if minimum is None:
            minimum = self.instance.processing_days_min
            cleaned['processing_days_min'] = minimum
        if maximum is None:
            maximum = self.instance.processing_days_max
            cleaned['processing_days_max'] = maximum
        if minimum is not None and maximum is not None and maximum < minimum:
            self.add_error('processing_days_max', _('Maximum processing time must be at least the minimum.'))
        return cleaned


class ShopMarketingForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['announcement', 'logo', 'banner', 'seo_title', 'seo_description']
        widgets = {
            'announcement': forms.Textarea(attrs={'class': 'field-textarea', 'rows': 3, 'placeholder': 'Share launches, deadlines, or your current story…'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'field-input', 'accept': 'image/*'}),
            'banner': forms.ClearableFileInput(attrs={'class': 'field-input', 'accept': 'image/*'}),
            'seo_title': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Optional search title'}),
            'seo_description': forms.Textarea(attrs={'class': 'field-textarea', 'rows': 3, 'placeholder': 'Optional search and social description'}),
        }


class ShopSectionForm(forms.Form):
    name = forms.CharField(max_length=80, widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'e.g. Wedding gifts'}))
    position = forms.IntegerField(min_value=0, max_value=999, initial=0, widget=forms.NumberInput(attrs={'class': 'field-input', 'min': 0}))
    is_visible = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'field-checkbox'}))
    listings = forms.ModelMultipleChoiceField(
        queryset=Listing.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        if shop is not None:
            self.fields['listings'].queryset = Listing.objects.filter(shop=shop).exclude(status=ListingStatus.ARCHIVED).order_by('title')
