from django import forms

from apps.accounts.constants import KENYA_COUNTIES
from apps.marketplace.shipping.models import ShippingProfile


class ShippingProfileForm(forms.ModelForm):
    counties = forms.MultipleChoiceField(
        choices=KENYA_COUNTIES,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'field-select', 'size': 8}),
        help_text='Leave empty to deliver to every county.',
    )

    class Meta:
        model = ShippingProfile
        fields = [
            'name', 'base_fee', 'additional_item_fee', 'free_shipping_threshold',
            'processing_days_min', 'processing_days_max', 'delivery_days_min', 'delivery_days_max',
            'counties', 'offers_delivery', 'allows_local_pickup', 'pickup_fee',
            'pickup_instructions', 'is_default', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'field-input'}),
            'base_fee': forms.NumberInput(attrs={'class': 'field-input', 'min': 0, 'step': '0.01'}),
            'additional_item_fee': forms.NumberInput(attrs={'class': 'field-input', 'min': 0, 'step': '0.01'}),
            'free_shipping_threshold': forms.NumberInput(attrs={'class': 'field-input', 'min': 0, 'step': '0.01', 'placeholder': 'Optional'}),
            'processing_days_min': forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
            'processing_days_max': forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
            'delivery_days_min': forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
            'delivery_days_max': forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
            'offers_delivery': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'allows_local_pickup': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'pickup_fee': forms.NumberInput(attrs={'class': 'field-input', 'min': 0, 'step': '0.01'}),
            'pickup_instructions': forms.Textarea(attrs={'class': 'field-textarea', 'rows': 3}),
            'is_default': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
        }

    def clean(self):
        cleaned = super().clean()
        for minimum, maximum in (
            ('processing_days_min', 'processing_days_max'),
            ('delivery_days_min', 'delivery_days_max'),
        ):
            if cleaned.get(minimum) is not None and cleaned.get(maximum) is not None and cleaned[maximum] < cleaned[minimum]:
                self.add_error(maximum, 'Maximum days must be at least the minimum.')
        if not cleaned.get('offers_delivery') and not cleaned.get('allows_local_pickup'):
            raise forms.ValidationError('Enable delivery, local pickup, or both.')
        return cleaned
