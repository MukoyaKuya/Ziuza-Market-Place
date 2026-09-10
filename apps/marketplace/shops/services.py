from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.accounts.permissions import ensure_authenticated
from apps.core.commerce_events import emit_commerce_event
from apps.marketplace.shops.models import LocalDeliveryScope, Shop, ShopVerificationStatus
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
    sub_county: str = '',
    ward: str = '',
    village: str = '',
    location_text: str = '',
    is_local_seller: bool = True,
    local_delivery_scope: str = LocalDeliveryScope.COUNTY,
    local_pickup_available: bool = True,
    local_pickup_instructions: str = '',
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
        sub_county=(sub_county or '').strip(),
        ward=(ward or '').strip(),
        village=(village or '').strip(),
        location_text=location_text.strip(),
        is_local_seller=bool(is_local_seller),
        local_delivery_scope=local_delivery_scope or LocalDeliveryScope.COUNTY,
        local_pickup_available=bool(local_pickup_available),
        local_pickup_instructions=(local_pickup_instructions or '').strip(),
        verification_status=ShopVerificationStatus.UNVERIFIED,
    )
    shop.save()
    transaction.on_commit(lambda: emit_commerce_event(
        'onboarding.shop_created', user_id=actor.id, shop_id=shop.id,
    ))
    return shop


@transaction.atomic
def update_shop_settings(*, actor: User, shop: Shop, **fields) -> Shop:
    """Update editable shop profile fields. Verification status is not seller-writable."""
    ensure_shop_owner(actor=actor, shop=shop)

    allowed = {
        'name',
        'description',
        'county',
        'sub_county',
        'ward',
        'village',
        'location_text',
        'whatsapp_number',
        'is_local_seller',
        'local_delivery_scope',
        'local_pickup_available',
        'local_pickup_instructions',
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

    # Keep slug stable after creation unless name change needs a new unique slug and slug empty
    shop.save()

    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(
        shop=shop,
        actor=actor,
        action='shop.settings_updated',
        target=shop,
        description='Updated shop profile and local settings.',
    )
    return shop


@transaction.atomic
def set_vacation_mode(*, actor: User, shop: Shop, enabled: bool) -> Shop:
    ensure_shop_owner(actor=actor, shop=shop)
    shop.vacation_mode = bool(enabled)
    shop.save(update_fields=['vacation_mode', 'updated_at'])

    from apps.marketplace.shops.team_services import audit_shop_action
    status_str = 'enabled' if enabled else 'disabled'
    audit_shop_action(
        shop=shop,
        actor=actor,
        action='shop.vacation_mode',
        target=shop,
        description=f'Vacation mode {status_str}.',
    )
    return shop
