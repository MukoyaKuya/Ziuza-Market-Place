import uuid
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.marketplace.notifications.models import (
    DeliveryStatus,
    DigestFrequency,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)

TYPE_CATEGORIES = {
    'order_placed': 'order_updates',
    'payment_confirmed': 'order_updates',
    'shipment_update': 'shipping_updates',
    'message': 'messages',
    'custom_order': 'messages',
    'custom_order_response': 'messages',
    'saved_search_match': 'saved_searches',
    'low_stock': 'inventory_updates',
    'verification_status': 'marketplace_updates',
    'moderation': 'marketplace_updates',
    'help_request': 'order_updates',
    'help_response': 'order_updates',
    'help_request_response': 'order_updates',
    'help_request_message': 'order_updates',
    'help_request_escalated': 'order_updates',
    'help_request_resolved': 'order_updates',
    'review_received': 'marketplace_updates',
    'review_response': 'marketplace_updates',
    'review_reminder': 'order_updates',
    'review_moderated': 'marketplace_updates',
}


def _next_digest_time(frequency, now):
    local = timezone.localtime(now)
    if frequency == DigestFrequency.DAILY:
        candidate = local.replace(hour=8, minute=0, second=0, microsecond=0)
        if candidate <= local:
            candidate += timedelta(days=1)
        return candidate
    if frequency == DigestFrequency.WEEKLY:
        days = (7 - local.weekday()) % 7
        candidate = (local + timedelta(days=days)).replace(hour=8, minute=0, second=0, microsecond=0)
        if candidate <= local:
            candidate += timedelta(days=7)
        return candidate
    return now


@transaction.atomic
def create_notification(*, recipient, type, title, body='', target_url=''):
    notification = Notification.objects.create(
        recipient=recipient,
        type=type[:64],
        title=title[:200],
        body=body,
        target_url=target_url[:500],
    )
    preference, _ = NotificationPreference.objects.get_or_create(user=recipient)
    category = TYPE_CATEGORIES.get(type, 'marketplace_updates')
    should_email = (
        recipient.is_active
        and bool(recipient.email)
        and preference.email_enabled
        and preference.digest_frequency != DigestFrequency.NEVER
        and getattr(preference, category, True)
    )
    if should_email:
        now = timezone.now()
        NotificationDelivery.objects.create(
            notification=notification,
            recipient=recipient,
            mode=preference.digest_frequency,
            available_at=_next_digest_time(preference.digest_frequency, now),
        )
    return notification


def _absolute_url(path):
    if not path:
        return ''
    if path.startswith(('http://', 'https://')):
        return path
    return f'{settings.PUBLIC_SITE_URL}/{path.lstrip("/")}'


def _send_group(deliveries):
    recipient = deliveries[0].recipient
    notifications = [delivery.notification for delivery in deliveries]
    if len(deliveries) == 1 and deliveries[0].mode == DigestFrequency.IMMEDIATE:
        notification = notifications[0]
        subject = notification.title
        body = notification.body
        url = _absolute_url(notification.target_url)
        if url:
            body = f'{body}\n\nOpen in Ziuza: {url}' if body else f'Open in Ziuza: {url}'
    else:
        subject = f'Your Ziuza {deliveries[0].get_mode_display().lower()}'
        rows = []
        for notification in notifications[:50]:
            row = f'• {notification.title}'
            if notification.body:
                row += f' — {notification.body}'
            if notification.target_url:
                row += f'\n  {_absolute_url(notification.target_url)}'
            rows.append(row)
        body = 'Here are your latest Ziuza updates:\n\n' + '\n'.join(rows)
    result = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient.email], fail_silently=False)
    if result != 1:
        raise RuntimeError('Email backend did not accept the message.')
    return result


@transaction.atomic
def apply_preference_to_pending(preference):
    now = timezone.now()
    deliveries = NotificationDelivery.objects.select_for_update().filter(
        recipient=preference.user,
        status=DeliveryStatus.PENDING,
    ).select_related('notification')
    for delivery in deliveries:
        category = TYPE_CATEGORIES.get(delivery.notification.type, 'marketplace_updates')
        allowed = (
            preference.email_enabled
            and preference.digest_frequency != DigestFrequency.NEVER
            and getattr(preference, category, True)
        )
        if not allowed:
            delivery.status = DeliveryStatus.CANCELLED
            delivery.save(update_fields=['status', 'updated_at'])
        else:
            delivery.mode = preference.digest_frequency
            delivery.available_at = _next_digest_time(preference.digest_frequency, now)
            delivery.save(update_fields=['mode', 'available_at', 'updated_at'])


def _claim(delivery_ids, now):
    with transaction.atomic():
        claim_token = uuid.uuid4()
        claimed = list(
            NotificationDelivery.objects.select_for_update()
            .filter(id__in=delivery_ids, status=DeliveryStatus.PENDING, available_at__lte=now)
            .select_related('recipient', 'notification')
            .order_by('available_at', 'created_at', 'id')
        )
        for delivery in claimed:
            delivery.status = DeliveryStatus.PROCESSING
            delivery.attempts += 1
            delivery.claim_token = claim_token
            delivery.processing_started_at = now
            delivery.save(update_fields=['status', 'attempts', 'claim_token', 'processing_started_at', 'updated_at'])
        return claimed


def _finish(deliveries, *, error=None):
    now = timezone.now()
    claim_tokens = {item.id: item.claim_token for item in deliveries}
    with transaction.atomic():
        locked = NotificationDelivery.objects.select_for_update().filter(
            id__in=claim_tokens,
            status=DeliveryStatus.PROCESSING,
        )
        for delivery in locked:
            if delivery.claim_token != claim_tokens[delivery.id]:
                continue
            if error is None:
                delivery.status = DeliveryStatus.SENT
                delivery.sent_at = now
                delivery.last_error = ''
                fields = ['status', 'sent_at', 'last_error', 'claim_token', 'processing_started_at', 'updated_at']
            else:
                delivery.last_error = str(error).replace('\n', ' ')[:500]
                if delivery.attempts >= 5:
                    delivery.status = DeliveryStatus.FAILED
                else:
                    delivery.status = DeliveryStatus.PENDING
                    delivery.available_at = now + timedelta(minutes=min(60, 5 * (2 ** (delivery.attempts - 1))))
                fields = ['status', 'available_at', 'last_error', 'claim_token', 'processing_started_at', 'updated_at']
            delivery.claim_token = None
            delivery.processing_started_at = None
            delivery.save(update_fields=fields)


def deliver_pending_notifications(*, limit=500, now=None):
    now = now or timezone.now()
    lease_cutoff = now - timedelta(minutes=15)
    NotificationDelivery.objects.filter(status=DeliveryStatus.PROCESSING).filter(
        Q(processing_started_at__lt=lease_cutoff)
        | Q(processing_started_at__isnull=True, updated_at__lt=lease_cutoff)
    ).update(
        status=DeliveryStatus.PENDING,
        available_at=now,
        claim_token=None,
        processing_started_at=None,
    )
    due = list(
        NotificationDelivery.objects.filter(status=DeliveryStatus.PENDING, available_at__lte=now)
        .order_by('available_at', 'created_at', 'id')
        .values('id', 'recipient_id', 'mode')[:limit]
    )
    groups = defaultdict(list)
    for row in due:
        key = (row['recipient_id'], row['mode']) if row['mode'] != DigestFrequency.IMMEDIATE else (row['id'], row['mode'])
        groups[key].append(row['id'])
    sent = failed = 0
    for ids in groups.values():
        deliveries = _claim(ids, now)
        if not deliveries:
            continue
        try:
            _send_group(deliveries)
        except Exception as exc:
            _finish(deliveries, error=exc)
            failed += len(deliveries)
        else:
            _finish(deliveries)
            sent += len(deliveries)
    return {'sent': sent, 'failed': failed}
