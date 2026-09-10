import uuid

from django.db import models

from apps.marketplace.orders.models import Order


class PaymentStatusChoice(models.TextChoices):
    INITIATED = 'initiated', 'Initiated'
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class CallbackOutcome(models.TextChoices):
    RECEIVED = 'received', 'Received'
    PROCESSED = 'processed', 'Processed'
    REJECTED = 'rejected', 'Rejected'


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    provider = models.CharField(max_length=40)
    provider_reference = models.CharField(max_length=120, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    status = models.CharField(max_length=20, choices=PaymentStatusChoice.choices, default=PaymentStatusChoice.INITIATED)
    initiated_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    raw_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                condition=models.Q(status='confirmed'),
                name='uniq_one_confirmed_payment_per_order',
            ),
        ]


class PaymentCallbackEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        related_name='callback_events',
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=40)
    provider_reference = models.CharField(max_length=120, blank=True, db_index=True)
    authenticated = models.BooleanField(default=False)
    payload = models.JSONField(default=dict, blank=True)
    outcome = models.CharField(max_length=20, choices=CallbackOutcome.choices, default=CallbackOutcome.RECEIVED)
    error_code = models.CharField(max_length=80, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-received_at']
