from django.contrib.auth import get_user_model

from apps.accounts.models import Address

User = get_user_model()


def list_addresses_for_user(*, user: User):
    return Address.objects.filter(user=user).order_by(
        '-is_default_shipping',
        '-is_default_billing',
        '-created_at',
    )


def get_address_for_user(*, user: User, address_id) -> Address:
    """Owned address lookup. Raises Address.DoesNotExist if missing/unauthorized."""
    return Address.objects.get(id=address_id, user=user)
