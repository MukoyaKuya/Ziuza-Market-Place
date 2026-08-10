import secrets
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings

from apps.accounts.permissions import ensure_authenticated
from apps.marketplace.cart.models import Cart
from apps.marketplace.cart.services import annotate_cart_totals, cart_line_unit_price
from apps.marketplace.listings.models import Inventory, ListingStatus
from apps.marketplace.orders.models import (
    FulfillmentStatus,
    Order,
    OrderItem,
    PaymentStatus,
    SellerOrder,
)


def _public_number() -> str:
    return f'ZIU-{secrets.token_hex(4).upper()}'


def _address_snapshot(address) -> dict:
    if address is None:
        return {}
    return {
        'recipient_name': address.recipient_name,
        'phone': address.phone,
        'address_line_1': address.address_line_1,
        'address_line_2': address.address_line_2,
        'city_or_town': address.city_or_town,
        'county': address.county,
        'postal_code': address.postal_code,
        'country': address.country,
    }


@transaction.atomic
def create_checkout_order(*, actor, cart: Cart, shipping_address, shipping_method_code: str = 'standard', shipping_fee: Decimal = Decimal('300.00'), shipping_breakdown=None, coupon_code: str = '') -> Order:
    ensure_authenticated(actor=actor)
    if shipping_address is not None and shipping_address.user_id != actor.id:
        raise ValidationError(_('Invalid shipping address.'))

    totals = annotate_cart_totals(cart)
    if not totals['lines']:
        raise ValidationError(_('Your cart is empty.'))

    for line in totals['lines']:
        if not line['is_available']:
            raise ValidationError(_('Cart contains unavailable items. Update quantities and try again.'))

    promotion = None
    discount = Decimal('0.00')
    if coupon_code.strip():
        from apps.marketplace.promotions.services import validate_promotion
        promotion, discount = validate_promotion(actor=actor, code=coupon_code, lines=totals['lines'], lock=True)

    # Reserve inventory
    for line in totals['lines']:
        item = line['item']
        if item.listing.product_type == 'digital':
            continue
        inv_qs = Inventory.objects.select_for_update().filter(listing=item.listing)
        inv = inv_qs.filter(variant=item.variant).first() if item.variant_id else inv_qs.filter(variant__isnull=True).first()
        if inv is None or inv.available_to_sell < item.quantity:
            raise ValidationError(_('Insufficient inventory for %(title)s') % {'title': item.listing.title})
        inv.quantity_reserved += item.quantity
        inv.save(update_fields=['quantity_reserved', 'updated_at'])

    order = Order.objects.create(
        public_number=_public_number(),
        buyer=actor,
        currency='KES',
        subtotal=totals['subtotal'],
        shipping_total=shipping_fee,
        discount_total=discount,
        promotion_code=promotion.code if promotion else '',
        grand_total=totals['subtotal'] + shipping_fee - discount,
        payment_status=PaymentStatus.PENDING,
        fulfillment_status=FulfillmentStatus.UNFULFILLED,
        shipping_address_snapshot=_address_snapshot(shipping_address),
        billing_address_snapshot=_address_snapshot(shipping_address),
        shipping_method_code=shipping_method_code,
        shipping_breakdown=shipping_breakdown or [],
        reservation_expires_at=timezone.now() + timedelta(
            minutes=getattr(settings, 'ORDER_RESERVATION_MINUTES', 30)
        ),
    )

    seller_orders: dict = {}
    for line in totals['lines']:
        item = line['item']
        shop = item.listing.shop
        if shop.id not in seller_orders:
            seller_orders[shop.id] = SellerOrder.objects.create(
                order=order,
                shop=shop,
                subtotal=Decimal('0.00'),
            )
        seller_order = seller_orders[shop.id]
        unit = cart_line_unit_price(item)
        line_total = unit * item.quantity
        seller_order.subtotal += line_total
        cover = item.listing.images.first()
        OrderItem.objects.create(
            order=order,
            seller_order=seller_order,
            shop=shop,
            listing_id=item.listing_id,
            variant_id=item.variant_id,
            variant_snapshot={
                'name': item.variant.name,
                'sku': item.variant.sku,
                'options': item.variant.option_summary,
            } if item.variant_id else {},
            title_snapshot=item.listing.title,
            sku_snapshot=item.listing.sku or '',
            unit_price=unit,
            quantity=item.quantity,
            line_total=line_total,
            image_reference=cover.image.url if cover else '',
            personalization_text=getattr(item, 'personalization_text', ''),
            personalization_data=getattr(item, 'personalization_data', {}),
            product_type_snapshot=item.listing.product_type,
        )
        seller_order.save(update_fields=['subtotal', 'updated_at'])

    cart.items.all().delete()
    if promotion:
        from apps.marketplace.promotions.services import reserve_redemption
        reserve_redemption(promotion=promotion, order=order, user=actor, discount_amount=discount)
    return order


@transaction.atomic
def mark_order_paid(*, order: Order) -> Order:
    """Idempotent paid transition + convert reserved stock to sold."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.payment_status == PaymentStatus.PAID:
        return order
    if order.reservation_released_at:
        raise ValidationError(_('Order inventory reservation has already been released.'))
    if order.payment_status not in {PaymentStatus.PENDING, PaymentStatus.PROCESSING}:
        raise ValidationError(_('Order cannot be marked paid from current state.'))

    for item in order.items.all():
        listing_id = item.listing_id
        if not listing_id:
            continue
        if item.product_type_snapshot == 'digital':
            continue
        inv_qs = Inventory.objects.select_for_update().filter(listing_id=listing_id)
        inv = (
            inv_qs.filter(variant_id=item.variant_id).first()
            if item.variant_id
            else inv_qs.filter(variant__isnull=True).first()
        )
        if inv:
            inv.quantity_available = max(0, inv.quantity_available - item.quantity)
            inv.quantity_reserved = max(0, inv.quantity_reserved - item.quantity)
            inv.save(update_fields=['quantity_available', 'quantity_reserved', 'updated_at'])
            listing = inv.listing
            if listing.status == ListingStatus.ACTIVE:
                has_stock = Inventory.objects.filter(listing=listing).exclude(
                    quantity_available__lte=models.F('quantity_reserved')
                ).exists()
                if not has_stock:
                    listing.status = ListingStatus.SOLD_OUT
                    listing.save(update_fields=['status', 'updated_at'])

    order.payment_status = PaymentStatus.PAID
    order.fulfillment_status = FulfillmentStatus.PROCESSING
    order.save(update_fields=['payment_status', 'fulfillment_status', 'updated_at'])
    from apps.marketplace.orders.models import DownloadGrant
    for item in order.items.filter(product_type_snapshot='digital'):
        DownloadGrant.objects.get_or_create(order_item=item, defaults={'buyer': order.buyer})
    for seller_order in order.seller_orders.prefetch_related('items'):
        if seller_order.items.exists() and not seller_order.items.exclude(product_type_snapshot='digital').exists():
            seller_order.fulfillment_status = FulfillmentStatus.DELIVERED
            seller_order.save(update_fields=['fulfillment_status', 'updated_at'])
    if not order.items.exclude(product_type_snapshot='digital').exists():
        order.fulfillment_status = FulfillmentStatus.DELIVERED
        order.save(update_fields=['fulfillment_status', 'updated_at'])
    from apps.marketplace.promotions.models import RedemptionStatus
    from apps.marketplace.promotions.services import update_redemption_status
    update_redemption_status(order=order, status=RedemptionStatus.REDEEMED)
    return order


@transaction.atomic
def release_order_inventory(*, order: Order, payment_status: str = PaymentStatus.CANCELLED) -> Order:
    """Idempotently release stock held by an order that will not be paid."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.payment_status == PaymentStatus.PAID or order.reservation_released_at:
        return order

    for item in order.items.all():
        if not item.listing_id:
            continue
        inventory = Inventory.objects.select_for_update().filter(
            listing_id=item.listing_id,
            variant_id=item.variant_id,
        ).first()
        if inventory:
            inventory.quantity_reserved = max(0, inventory.quantity_reserved - item.quantity)
            inventory.save(update_fields=['quantity_reserved', 'updated_at'])

    order.payment_status = payment_status
    order.reservation_released_at = timezone.now()
    order.save(update_fields=['payment_status', 'reservation_released_at', 'updated_at'])
    from apps.marketplace.promotions.models import RedemptionStatus
    from apps.marketplace.promotions.services import update_redemption_status
    update_redemption_status(order=order, status=RedemptionStatus.RELEASED)
    return order


def cancel_order(*, actor, order: Order) -> Order:
    ensure_authenticated(actor=actor)
    if order.buyer_id != actor.id:
        raise ValidationError(_('You cannot cancel this order.'))
    if order.payment_status not in {PaymentStatus.PENDING, PaymentStatus.PROCESSING}:
        raise ValidationError(_('This order can no longer be cancelled.'))
    return release_order_inventory(order=order, payment_status=PaymentStatus.CANCELLED)


def expire_stale_orders(*, now=None) -> int:
    """Release all overdue unpaid reservations. Safe to run repeatedly."""
    now = now or timezone.now()
    order_ids = list(
        Order.objects.filter(
            reservation_expires_at__lte=now,
            reservation_released_at__isnull=True,
            payment_status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING],
        ).values_list('pk', flat=True)
    )
    for order_id in order_ids:
        release_order_inventory(order=Order(pk=order_id), payment_status=PaymentStatus.CANCELLED)
    return len(order_ids)
