from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.marketplace.listings.models import ProductType
from apps.marketplace.shipping.models import ShippingProfile, available_shipping_methods
from apps.marketplace.shops.permissions import MANAGE_SHIPPING, ensure_shop_permission


@dataclass(frozen=True)
class ShippingQuote:
    code: str
    name: str
    fee: Decimal
    estimated_days_min: int
    estimated_days_max: int
    is_pickup: bool
    breakdown: list

    @property
    def base_fee(self):
        return self.fee


@transaction.atomic
def save_shipping_profile(*, actor, shop, profile=None, **fields):
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_SHIPPING)
    if profile is not None and profile.shop_id != shop.id:
        raise ValidationError('Shipping profile does not belong to this shop.')
    if profile is None:
        profile = ShippingProfile(shop=shop)
    for key, value in fields.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    if profile.is_default:
        shop.shipping_profiles.exclude(pk=profile.pk).update(is_default=False)
    profile.full_clean()
    profile.save()
    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(
        shop=shop, actor=actor, action='shipping_profile.saved', target=profile,
        description=f'Saved shipping profile “{profile.name}”.',
    )
    return profile


@transaction.atomic
def delete_shipping_profile(*, actor, shop, profile):
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_SHIPPING)
    if profile.shop_id != shop.id:
        raise ValidationError('Shipping profile does not belong to this shop.')
    name = profile.name
    profile.delete()
    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(shop=shop, actor=actor, action='shipping_profile.deleted', description=f'Deleted shipping profile “{name}”.')


def _fallback_quotes(*, county):
    return [ShippingQuote(
        code=method.code,
        name=method.name,
        fee=method.base_fee,
        estimated_days_min=method.estimated_days_min,
        estimated_days_max=method.estimated_days_max,
        is_pickup=method.is_pickup,
        breakdown=[{'source': 'global', 'name': method.name, 'fee': str(method.base_fee)}],
    ) for method in available_shipping_methods(county=county)]


def calculate_shipping_quotes(*, lines, county: str = '') -> list[ShippingQuote]:
    physical = [line for line in lines if line['item'].listing.product_type != ProductType.DIGITAL]
    if not physical:
        return []
    profiles = [line['item'].listing.shipping_profile for line in physical]
    if any(profile is None or not profile.is_active for profile in profiles):
        return _fallback_quotes(county=county)

    grouped = {}
    shops = set()
    for line, profile in zip(physical, profiles, strict=False):
        shops.add(line['item'].listing.shop_id)
        group = grouped.setdefault(profile.id, {
            'profile': profile,
            'quantity': 0,
            'subtotal': Decimal('0.00'),
            'shop_name': line['item'].listing.shop.name,
        })
        group['quantity'] += line['item'].quantity
        group['subtotal'] += line['line_total']

    quotes = []
    if all(group['profile'].offers_delivery and group['profile'].covers_county(county) for group in grouped.values()):
        fee = Decimal('0.00')
        minimums = []
        maximums = []
        breakdown = []
        for group in grouped.values():
            profile = group['profile']
            group_fee = profile.base_fee + profile.additional_item_fee * max(0, group['quantity'] - 1)
            if profile.free_shipping_threshold is not None and group['subtotal'] >= profile.free_shipping_threshold:
                group_fee = Decimal('0.00')
            fee += group_fee
            minimums.append(profile.processing_days_min + profile.delivery_days_min)
            maximums.append(profile.processing_days_max + profile.delivery_days_max)
            breakdown.append({
                'shop': group['shop_name'], 'shop_id': str(profile.shop_id), 'profile': profile.name, 'fee': str(group_fee),
                'quantity': group['quantity'], 'pickup': False,
            })
        quotes.append(ShippingQuote(
            code='seller_delivery', name='Seller delivery', fee=fee,
            estimated_days_min=min(minimums), estimated_days_max=max(maximums),
            is_pickup=False, breakdown=breakdown,
        ))

    if len(shops) == 1 and all(group['profile'].allows_local_pickup for group in grouped.values()):
        fee = sum((group['profile'].pickup_fee for group in grouped.values()), Decimal('0.00'))
        quotes.append(ShippingQuote(
            code='seller_pickup', name='Local pickup', fee=fee,
            estimated_days_min=min(group['profile'].processing_days_min for group in grouped.values()),
            estimated_days_max=max(group['profile'].processing_days_max for group in grouped.values()),
            is_pickup=True,
            breakdown=[{
                'shop': group['shop_name'], 'shop_id': str(group['profile'].shop_id), 'profile': group['profile'].name,
                'fee': str(group['profile'].pickup_fee), 'pickup': True,
                'instructions': group['profile'].pickup_instructions,
            } for group in grouped.values()],
        ))
    return quotes
