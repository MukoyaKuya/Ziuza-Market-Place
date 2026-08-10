from django import forms

from apps.marketplace.notifications.models import NotificationPreference


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            'email_enabled', 'digest_frequency', 'order_updates', 'messages',
            'shipping_updates', 'marketplace_updates', 'saved_searches', 'inventory_updates',
        ]
        widgets = {
            'email_enabled': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'digest_frequency': forms.Select(attrs={'class': 'field-select'}),
            'order_updates': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'messages': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'shipping_updates': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'marketplace_updates': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'saved_searches': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'inventory_updates': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
        }
        labels = {
            'email_enabled': 'Send notification emails',
            'digest_frequency': 'Email frequency',
            'order_updates': 'Orders and support cases',
            'messages': 'Messages and custom orders',
            'shipping_updates': 'Shipping and delivery',
            'marketplace_updates': 'Account, verification, and marketplace updates',
            'saved_searches': 'Saved-search matches',
            'inventory_updates': 'Seller inventory alerts',
        }
