import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    type = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    target_url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class DigestFrequency(models.TextChoices):
    IMMEDIATE = 'immediate', 'Immediately'
    DAILY = 'daily', 'Daily digest'
    WEEKLY = 'weekly', 'Weekly digest'
    NEVER = 'never', 'Never email me'


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
    )
    email_enabled = models.BooleanField(default=True)
    digest_frequency = models.CharField(max_length=16, choices=DigestFrequency.choices, default=DigestFrequency.IMMEDIATE)
    order_updates = models.BooleanField(default=True)
    messages = models.BooleanField(default=True)
    shipping_updates = models.BooleanField(default=True)
    marketplace_updates = models.BooleanField(default=True)
    saved_searches = models.BooleanField(default=True)
    inventory_updates = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Notification preferences for {self.user}'


class DeliveryStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class NotificationDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='deliveries')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_deliveries')
    channel = models.CharField(max_length=16, default='email')
    mode = models.CharField(max_length=16, choices=DigestFrequency.choices, default=DigestFrequency.IMMEDIATE)
    status = models.CharField(max_length=16, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING, db_index=True)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['available_at', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['notification', 'channel'], name='uniq_notification_delivery_channel'),
        ]
        indexes = [models.Index(fields=['status', 'available_at'])]

    def __str__(self):
        return f'{self.channel} for {self.notification}'


def notify(*, recipient, type: str, title: str, body: str = '', target_url: str = '') -> Notification:
    from apps.marketplace.notifications.delivery import create_notification

    return create_notification(
        recipient=recipient, type=type, title=title, body=body, target_url=target_url
    )


def mark_notification_read(*, actor, notification_id) -> Notification:
    notification = Notification.objects.get(id=notification_id, recipient=actor)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return notification
