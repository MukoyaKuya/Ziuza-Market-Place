import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.marketplace.orders.storage import CaseEvidenceStorage


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    PROCESSING = 'processing', _('Processing')
    PAID = 'paid', _('Paid')
    FAILED = 'failed', _('Failed')
    CANCELLED = 'cancelled', _('Cancelled')
    PARTIALLY_REFUNDED = 'partially_refunded', _('Partially refunded')
    REFUNDED = 'refunded', _('Refunded')


class FulfillmentStatus(models.TextChoices):
    UNFULFILLED = 'unfulfilled', _('Unfulfilled')
    PROCESSING = 'processing', _('Processing')
    READY = 'ready', _('Ready')
    SHIPPED = 'shipped', _('Shipped')
    PARTIALLY_SHIPPED = 'partially_shipped', _('Partially shipped')
    DELIVERED = 'delivered', _('Delivered')
    CANCELLED = 'cancelled', _('Cancelled')


class HelpRequestStatus(models.TextChoices):
    OPEN = 'open', _('Open')
    SELLER_RESPONDED = 'seller_responded', _('Seller responded')
    ESCALATED = 'escalated', _('Escalated to Ziuza')
    RESOLVED = 'resolved', _('Resolved')
    CLOSED = 'closed', _('Closed')


class HelpRequestReason(models.TextChoices):
    NOT_RECEIVED = 'not_received', _('Item not received')
    LATE = 'late', _('Delivery is late')
    DAMAGED = 'damaged', _('Item arrived damaged')
    NOT_AS_DESCRIBED = 'not_as_described', _('Item not as described')
    WRONG_ITEM = 'wrong_item', _('Wrong item received')
    OTHER = 'other', _('Other problem')


class ProtectionCaseType(models.TextChoices):
    SUPPORT = 'support', _('Order support')
    RETURN = 'return', _('Return request')
    EXCHANGE = 'exchange', _('Exchange request')
    BUYER_PROTECTION = 'buyer_protection', _('Buyer protection case')


class RequestedOutcome(models.TextChoices):
    REPLACEMENT = 'replacement', _('Replacement')
    RETURN_REFUND = 'return_refund', _('Return and refund')
    EXCHANGE = 'exchange', _('Exchange')
    PARTIAL_REFUND = 'partial_refund', _('Partial refund')
    OTHER = 'other', _('Other resolution')


class CaseResolutionOutcome(models.TextChoices):
    BUYER = 'buyer', _('Resolved for buyer')
    SELLER = 'seller', _('Resolved for seller')
    AGREEMENT = 'agreement', _('Buyer and seller agreement')
    NO_ACTION = 'no_action', _('Closed without action')


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_number = models.CharField(max_length=32, unique=True, db_index=True)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    currency = models.CharField(max_length=3, default='KES')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    promotion_code = models.CharField(max_length=32, blank=True)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_status = models.CharField(max_length=32, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    fulfillment_status = models.CharField(
        max_length=32, choices=FulfillmentStatus.choices, default=FulfillmentStatus.UNFULFILLED
    )
    shipping_address_snapshot = models.JSONField(default=dict)
    billing_address_snapshot = models.JSONField(default=dict)
    shipping_method_code = models.CharField(max_length=64, blank=True)
    shipping_breakdown = models.JSONField(default=list, blank=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reservation_released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class SellerOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='seller_orders')
    shop = models.ForeignKey('shops.Shop', on_delete=models.PROTECT, related_name='seller_orders')
    fulfillment_status = models.CharField(
        max_length=32, choices=FulfillmentStatus.choices, default=FulfillmentStatus.UNFULFILLED
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    seller_order = models.ForeignKey(SellerOrder, on_delete=models.CASCADE, related_name='items')
    shop = models.ForeignKey('shops.Shop', on_delete=models.PROTECT)
    listing_id = models.UUIDField(null=True, blank=True)
    variant_id = models.UUIDField(null=True, blank=True)
    variant_snapshot = models.JSONField(default=dict, blank=True)
    title_snapshot = models.CharField(max_length=200)
    sku_snapshot = models.CharField(max_length=64, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    image_reference = models.CharField(max_length=500, blank=True)
    personalization_text = models.TextField(blank=True, default='')
    personalization_data = models.JSONField(default=dict, blank=True)
    product_type_snapshot = models.CharField(max_length=20, default='physical')


class DownloadGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name='download_grant')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='download_grants')
    granted_at = models.DateTimeField(auto_now_add=True)
    download_count = models.PositiveIntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class HelpRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='help_requests')
    seller_order = models.ForeignKey(SellerOrder, on_delete=models.CASCADE, related_name='help_requests')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='help_requests')
    case_type = models.CharField(max_length=32, choices=ProtectionCaseType.choices, default=ProtectionCaseType.SUPPORT, db_index=True)
    reason = models.CharField(max_length=32, choices=HelpRequestReason.choices)
    status = models.CharField(max_length=32, choices=HelpRequestStatus.choices, default=HelpRequestStatus.OPEN, db_index=True)
    description = models.TextField()
    desired_resolution = models.CharField(max_length=200, blank=True)
    requested_outcome = models.CharField(max_length=32, choices=RequestedOutcome.choices, blank=True)
    seller_response = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    resolution_outcome = models.CharField(max_length=32, choices=CaseResolutionOutcome.choices, blank=True)
    refund_recommendation = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='moderated_protection_cases')
    response_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    first_seller_response_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['seller_order', 'status'], name='orders_help_seller__65a8ac_idx')]


class ProtectionCaseMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(HelpRequest, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='protection_case_messages')
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class ProtectionCaseEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(HelpRequest, on_delete=models.CASCADE, related_name='evidence')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='protection_case_evidence')
    file = models.FileField(storage=CaseEvidenceStorage(), upload_to='%Y/%m/%d')
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    description = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class ProtectionCaseEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(HelpRequest, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='protection_case_events')
    action = models.CharField(max_length=64, db_index=True)
    note = models.CharField(max_length=300, blank=True)
    is_internal = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
