from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

User = get_user_model()


def register_user(*, email: str, password: str, display_name: str = '', phone: str = '') -> User:
    """Create a new buyer/seller-capable account. Seller status comes from shops later."""
    email = User.objects.normalize_email(email).strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({'email': _('A user with this email address already exists.')})

    return User.objects.create_user(
        email=email,
        password=password,
        display_name=display_name,
        phone=phone,
    )


def update_user_profile(
    *,
    actor: User,
    display_name: str,
    first_name: str = '',
    last_name: str = '',
    phone: str = '',
) -> User:
    """Update profile fields for the authenticated actor only."""
    actor.display_name = display_name
    actor.first_name = first_name
    actor.last_name = last_name
    actor.phone = phone
    actor.save(update_fields=['display_name', 'first_name', 'last_name', 'phone', 'updated_at'])
    return actor
