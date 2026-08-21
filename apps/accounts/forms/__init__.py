from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _

from apps.accounts.constants import KENYA_COUNTIES
from apps.accounts.models import Address

User = get_user_model()


class RegistrationForm(forms.Form):
    email = forms.EmailField(
        label=_('Email'),
        max_length=255,
        widget=forms.EmailInput(attrs={
            'class': 'field-input',
            'autocomplete': 'email',
            'placeholder': 'you@example.com',
        }),
    )
    display_name = forms.CharField(
        label=_('Display name'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'field-input',
            'autocomplete': 'nickname',
            'placeholder': 'How buyers see you',
        }),
    )
    phone = forms.CharField(
        label=_('Phone'),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'field-input',
            'autocomplete': 'tel',
            'placeholder': '+254…',
        }),
    )
    password1 = forms.CharField(
        label=_('Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'autocomplete': 'new-password',
        }),
    )
    password2 = forms.CharField(
        label=_('Confirm password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'autocomplete': 'new-password',
        }),
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', _('Passwords do not match.'))
        if password1:
            try:
                validate_password(password1)
            except DjangoValidationError as exc:
                self.add_error('password1', exc)
        return cleaned


class LoginForm(forms.Form):
    email = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={
            'class': 'field-input',
            'autocomplete': 'email',
        }),
    )
    password = forms.CharField(
        label=_('Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'autocomplete': 'current-password',
        }),
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class ProfileForm(forms.Form):
    display_name = forms.CharField(
        label=_('Display name'),
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'nickname'}),
    )
    first_name = forms.CharField(
        label=_('First name'),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        label=_('Last name'),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'family-name'}),
    )
    phone = forms.CharField(
        label=_('Phone'),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'tel'}),
    )

    @classmethod
    def from_user(cls, user: User) -> 'ProfileForm':
        return cls(initial={
            'display_name': user.display_name,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': user.phone,
        })


class AddressForm(forms.ModelForm):
    county = forms.ChoiceField(
        choices=KENYA_COUNTIES,
        widget=forms.Select(attrs={'class': 'field-select'}),
    )

    class Meta:
        model = Address
        fields = [
            'recipient_name',
            'phone',
            'address_line_1',
            'address_line_2',
            'city_or_town',
            'county',
            'postal_code',
            'country',
            'is_default_shipping',
            'is_default_billing',
        ]
        widgets = {
            'recipient_name': forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'name'}),
            'phone': forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'tel'}),
            'address_line_1': forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'address-line1'}),
            'address_line_2': forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'address-line2'}),
            'city_or_town': forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'address-level2'}),
            'postal_code': forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'postal-code'}),
            'country': forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'country-name'}),
            'is_default_shipping': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
            'is_default_billing': forms.CheckboxInput(attrs={'class': 'field-checkbox'}),
        }
        labels = {
            'is_default_shipping': _('Default shipping address'),
            'is_default_billing': _('Default billing address'),
        }
