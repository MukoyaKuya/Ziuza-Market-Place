from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.accounts.permissions import ensure_authenticated
from apps.marketplace.shops.models import Shop, ShopVerificationStatus
from apps.marketplace.shops.permissions import ensure_shop_owner
from apps.marketplace.shops.selectors import get_shop_for_user

User = get_user_model()


@transaction.atomic
def create_shop(
    *,
    actor: User,
    name: str,
    description: str = '',
    county: str = 'Nairobi',
    location_text: str = '',
) -> Shop:
    """Onboard a seller by creating their shop. One shop per owner (MVP)."""
    ensure_authenticated(actor=actor)
    if get_shop_for_user(user=actor) is not None:
        raise ValidationError({'name': _('You already have a shop on Ziuza.')})

    name = (name or '').strip()
    if not name:
        raise ValidationError({'name': _('Shop name is required.')})

    shop = Shop(
        owner=actor,
        name=name,
        description=description.strip(),
        county=county or 'Nairobi',
        location_text=location_text.strip(),
        verification_status=ShopVerificationStatus.UNVERIFIED,
    )
    shop.save()
    return shop


@transaction.atomic
def update_shop_settings(*, actor: User, shop: Shop, **fields) -> Shop:
    """Update editable shop profile fields. Verification status is not seller-writable."""
    ensure_shop_owner(actor=actor, shop=shop)

    allowed = {
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
    }
    for key, value in fields.items():
        if key not in allowed:
            continue
        setattr(shop, key, value)

    # Keep slug stable after creation unless name change needs a new unique slug and slug empty — leave slug as-is for URL stability.
    shop.save()
    return shop


@transaction.atomic
def set_vacation_mode(*, actor: User, shop: Shop, enabled: bool) -> Shop:
    ensure_shop_owner(actor=actor, shop=shop)
    shop.vacation_mode = bool(enabled)
    shop.save(update_fields=['vacation_mode', 'updated_at'])
    return shop
