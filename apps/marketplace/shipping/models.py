import uuid
from decimal import Decimal

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone

from apps.marketplace.orders.models import FulfillmentStatus, SellerOrder
from apps.marketplace.shops.permissions import MANAGE_ORDERS, ensure_shop_permission


class ShippingMethod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    base_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    estimated_days_min = models.PositiveSmallIntegerField(default=1)
    estimated_days_max = models.PositiveSmallIntegerField(default=5)
    counties = models.JSONField(default=list, blank=True, help_text='Empty means all counties.')
    is_pickup = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)


class ShippingProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='shipping_profiles')
    name = models.CharField(max_length=120)
    base_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    additional_item_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    free_shipping_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.00'))])
    processing_days_min = models.PositiveSmallIntegerField(default=1)
    processing_days_max = models.PositiveSmallIntegerField(default=3)
    delivery_days_min = models.PositiveSmallIntegerField(default=1)
    delivery_days_max = models.PositiveSmallIntegerField(default=5)
    counties = models.JSONField(default=list, blank=True, help_text='Empty means delivery to all counties.')
    offers_delivery = models.BooleanField(default=True)
    allows_local_pickup = models.BooleanField(default=False)
    pickup_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    pickup_instructions = models.CharField(max_length=300, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['shop', 'name'], name='uniq_shop_shipping_profile_name'),
            models.UniqueConstraint(fields=['shop'], condition=models.Q(is_default=True), name='uniq_default_shipping_profile_per_shop'),
        ]

    def __str__(self):
        return f'{self.shop}: {self.name}'

    def covers_county(self, county: str) -> bool:
        return not self.counties or county in self.counties

    def clean(self):
        if self.processing_days_max < self.processing_days_min:
            raise ValidationError({'processing_days_max': 'Maximum processing days must be at least the minimum.'})
        if self.delivery_days_max < self.delivery_days_min:
            raise ValidationError({'delivery_days_max': 'Maximum delivery days must be at least the minimum.'})
        if not self.offers_delivery and not self.allows_local_pickup:
            raise ValidationError('Enable delivery, local pickup, or both.')


class Shipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller_order = models.ForeignKey(SellerOrder, on_delete=models.CASCADE, related_name='shipments')
    carrier = models.CharField(max_length=120, blank=True)
    tracking_number = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=32, choices=FulfillmentStatus.choices, default=FulfillmentStatus.PROCESSING)
    estimated_delivery_date = models.DateField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ShipmentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=32, choices=FulfillmentStatus.choices)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


FULFILLMENT_TRANSITIONS = {
    FulfillmentStatus.UNFULFILLED: {FulfillmentStatus.PROCESSING, FulfillmentStatus.CANCELLED},
    FulfillmentStatus.PROCESSING: {FulfillmentStatus.READY, FulfillmentStatus.SHIPPED, FulfillmentStatus.CANCELLED},
    FulfillmentStatus.READY: {FulfillmentStatus.SHIPPED, FulfillmentStatus.CANCELLED},
    FulfillmentStatus.SHIPPED: {FulfillmentStatus.DELIVERED},
    FulfillmentStatus.DELIVERED: set(),
    FulfillmentStatus.CANCELLED: set(),
}


def available_shipping_methods(*, county: str = ''):
    methods = ShippingMethod.objects.filter(is_active=True).order_by('base_fee', 'name')
    return [method for method in methods if not method.counties or county in method.counties]


def _sync_order_fulfillment(order):
    statuses = list(order.seller_orders.values_list('fulfillment_status', flat=True))
    if statuses and all(status == FulfillmentStatus.DELIVERED for status in statuses):
        aggregate = FulfillmentStatus.DELIVERED
    elif statuses and all(status == FulfillmentStatus.CANCELLED for status in statuses):
        aggregate = FulfillmentStatus.CANCELLED
    elif any(status == FulfillmentStatus.SHIPPED for status in statuses):
        aggregate = FulfillmentStatus.SHIPPED if all(status == FulfillmentStatus.SHIPPED for status in statuses) else FulfillmentStatus.PARTIALLY_SHIPPED
    elif any(status in {FulfillmentStatus.PROCESSING, FulfillmentStatus.READY} for status in statuses):
        aggregate = FulfillmentStatus.PROCESSING
    else:
        aggregate = FulfillmentStatus.UNFULFILLED
    order.fulfillment_status = aggregate
    order.save(update_fields=['fulfillment_status', 'updated_at'])


@transaction.atomic
def update_seller_fulfillment(*, actor, seller_order: SellerOrder, status: str, tracking_number: str = '', carrier: str = '', note: str = ''):
    ensure_shop_permission(actor=actor, shop=seller_order.shop, permission=MANAGE_ORDERS)
    if seller_order.order.payment_status != 'paid':
        raise ValidationError('Only paid orders can be fulfilled.')
    allowed = FULFILLMENT_TRANSITIONS.get(seller_order.fulfillment_status, set())
    if status not in allowed:
        raise ValidationError(f'Cannot move from {seller_order.get_fulfillment_status_display()} to {status}.')
    if status == FulfillmentStatus.SHIPPED and (not carrier.strip() or not tracking_number.strip()):
        raise ValidationError('Carrier and tracking number are required when marking an order shipped.')
    seller_order.fulfillment_status = status
    seller_order.save(update_fields=['fulfillment_status', 'updated_at'])
    shipment = seller_order.shipments.order_by('-created_at').first()
    if shipment is None:
        shipment = Shipment.objects.create(seller_order=seller_order)
    shipment.status = status
    if carrier:
        shipment.carrier = carrier.strip()
    if tracking_number:
        shipment.tracking_number = tracking_number.strip()
    if status == FulfillmentStatus.SHIPPED and not shipment.shipped_at:
        shipment.shipped_at = timezone.now()
    if status == FulfillmentStatus.DELIVERED and not shipment.delivered_at:
        shipment.delivered_at = timezone.now()
    shipment.save()
    ShipmentEvent.objects.create(shipment=shipment, status=status, note=note.strip()[:300])
    _sync_order_fulfillment(seller_order.order)
    from apps.marketplace.notifications.services import notify

    notify(
        recipient=seller_order.order.buyer,
        type='shipment_update',
        title=f'Order {seller_order.order.public_number}: {seller_order.get_fulfillment_status_display()}',
        body=f'{seller_order.shop.name} updated your delivery.' + (f' Tracking: {shipment.tracking_number}' if shipment.tracking_number else ''),
        target_url=f'/account/orders/{seller_order.order.public_number}/',
    )
    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(
        shop=seller_order.shop, actor=actor, action='order.fulfillment_updated', target=seller_order,
        description=f'Changed order {seller_order.order.public_number} to {seller_order.get_fulfillment_status_display()}.',
    )
    return seller_order
