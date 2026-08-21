import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.marketplace.cart.models import Cart, CartItem
from apps.marketplace.listings.models import Inventory, Listing, ListingStatus, ListingVariant


def validate_personalization(*, listing: Listing, submitted: dict, legacy_text: str = '') -> dict:
    fields = list(listing.personalization_fields.all())
    if not fields:
        return {'Personalization': legacy_text.strip()} if legacy_text.strip() else {}
    result = {}
    for field in fields:
        value = str(submitted.get(str(field.id), '')).strip()
        if field.is_required and not value:
            raise ValidationError(_('%(label)s is required.') % {'label': field.label})
        if not value:
            continue
        if len(value) > field.max_length:
            raise ValidationError(_('%(label)s is too long.') % {'label': field.label})
        if field.field_type == 'select' and value not in field.options:
            raise ValidationError(_('Choose a valid option for %(label)s.') % {'label': field.label})
        result[field.label] = value
    return result


def get_or_create_cart(*, request) -> Cart:
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user, defaults={'session_key': ''})
        return cart
    if not request.session.session_key:
        request.session.create()
    cart, _ = Cart.objects.get_or_create(
        session_key=request.session.session_key,
        user=None,
    )
    return cart


def _available_qty(listing: Listing, variant: ListingVariant | None) -> int:
    if listing.product_type == 'digital':
        return 999999
    if variant:
        inv = Inventory.objects.filter(listing=listing, variant=variant).first()
    else:
        inv = Inventory.objects.filter(listing=listing, variant__isnull=True).first()
    return inv.available_to_sell if inv else 0


@transaction.atomic
def add_to_cart(*, request, listing: Listing, quantity: int = 1, variant: ListingVariant | None = None,
                 personalization_text: str = '', personalization_data: dict | None = None) -> CartItem:
    if listing.status != ListingStatus.ACTIVE or not listing.shop.is_publicly_visible:
        raise ValidationError(_('This listing is not available for purchase.'))
    if variant and variant.listing_id != listing.id:
        raise ValidationError(_('Variant does not belong to this listing.'))
    if listing.variants.filter(is_active=True).exists() and variant is None:
        raise ValidationError(_('Choose an available option before adding this item.'))
    if variant and not variant.is_active:
        raise ValidationError(_('This option is not available.'))
    if quantity < 1:
        raise ValidationError({'quantity': _('Quantity must be at least 1.')})
    available = _available_qty(listing, variant)
    if quantity > available:
        raise ValidationError(_('Not enough inventory available.'))

    cart = get_or_create_cart(request=request)
    validated_personalization = validate_personalization(
        listing=listing,
        submitted=personalization_data or {},
        legacy_text=personalization_text,
    )
    signature = hashlib.sha256(json.dumps(validated_personalization, sort_keys=True).encode()).hexdigest()
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        listing=listing,
        variant=variant,
        personalization_signature=signature,
        defaults={'quantity': quantity, 'personalization_text': personalization_text, 'personalization_data': validated_personalization},
    )
    if not created:
        new_qty = item.quantity + quantity
        if new_qty > available:
            raise ValidationError(_('Not enough inventory available.'))
        item.quantity = new_qty
        if personalization_text:
            item.personalization_text = personalization_text
        item.personalization_data = validated_personalization
        item.save(update_fields=['quantity', 'personalization_text', 'personalization_data', 'updated_at'])
    cart.save(update_fields=['updated_at'])
    return item


@transaction.atomic
def update_cart_item_quantity(*, request, item_id, quantity: int) -> CartItem:
    cart = get_or_create_cart(request=request)
    try:
        item = CartItem.objects.select_related('listing').get(id=item_id, cart=cart)
    except CartItem.DoesNotExist as exc:
        raise ValidationError(_('Cart item not found.')) from exc
    if quantity < 1:
        item.delete()
        return item
    available = _available_qty(item.listing, item.variant)
    if quantity > available:
        raise ValidationError(_('Not enough inventory available.'))
    item.quantity = quantity
    item.save(update_fields=['quantity', 'updated_at'])
    return item


@transaction.atomic
def remove_cart_item(*, request, item_id) -> None:
    cart = get_or_create_cart(request=request)
    CartItem.objects.filter(id=item_id, cart=cart).delete()


def cart_line_unit_price(item: CartItem):
    if item.variant_id and item.variant and item.variant.price_override is not None:
        return item.variant.price_override
    return item.listing.base_price


def annotate_cart_totals(cart: Cart) -> dict:
    items = list(
        cart.items.select_related(
            'listing', 'listing__shop', 'listing__shipping_profile', 'variant',
        ).prefetch_related('listing__images', 'listing__personalization_fields')
    )
    lines = []
    subtotal = 0
    for item in items:
        unit = cart_line_unit_price(item)
        line_total = unit * item.quantity
        subtotal += line_total
        lines.append(
            {
                'item': item,
                'unit_price': unit,
                'line_total': line_total,
                'available': _available_qty(item.listing, item.variant),
                'is_available': item.listing.status == ListingStatus.ACTIVE
                and _available_qty(item.listing, item.variant) >= item.quantity,
            }
        )
    return {'cart': cart, 'lines': lines, 'subtotal': subtotal, 'item_count': sum(i.quantity for i in items)}


def purge_inactive_anonymous_carts(*, days: int = 30) -> int:
    """Purge anonymous carts that have not been modified for more than `days` days."""
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(days=days)
    deleted_count, _ = Cart.objects.filter(user__isnull=True, updated_at__lt=cutoff).delete()
    return deleted_count
