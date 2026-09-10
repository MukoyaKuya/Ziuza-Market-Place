from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import EmailOTP
from apps.marketplace.notifications.models import DeliveryStatus, Notification, NotificationDelivery
from apps.marketplace.payments.models import PaymentCallbackEvent
from apps.marketplace.search.models import RecentlyViewedListing


def purge_operational_data(*, execute: bool = False) -> dict[str, int]:
    """Report or purge non-transactional data using configured retention windows."""
    now = timezone.now()
    otp_cutoff = now - timedelta(days=settings.RETENTION_OTP_DAYS)
    recent_cutoff = now - timedelta(days=settings.RETENTION_RECENT_VIEWS_DAYS)
    delivery_cutoff = now - timedelta(days=settings.RETENTION_DELIVERY_DAYS)
    notification_cutoff = now - timedelta(days=settings.RETENTION_READ_NOTIFICATION_DAYS)
    callback_cutoff = now - timedelta(days=settings.RETENTION_CALLBACK_PAYLOAD_DAYS)

    querysets = {
        'email_otps': EmailOTP.objects.filter(
            Q(expires_at__lt=otp_cutoff) | Q(consumed_at__lt=otp_cutoff)
        ),
        'expired_sessions': Session.objects.filter(expire_date__lt=now),
        'recent_views': RecentlyViewedListing.objects.filter(last_viewed_at__lt=recent_cutoff),
        'deliveries': NotificationDelivery.objects.filter(
            status__in=[DeliveryStatus.SENT, DeliveryStatus.FAILED, DeliveryStatus.CANCELLED],
            updated_at__lt=delivery_cutoff,
        ),
        'read_notifications': Notification.objects.filter(
            is_read=True,
            created_at__lt=notification_cutoff,
        ),
        'callback_payloads': PaymentCallbackEvent.objects.exclude(payload={}).filter(received_at__lt=callback_cutoff),
    }
    counts = {name: queryset.count() for name, queryset in querysets.items()}
    if not execute:
        return counts

    for name in ('email_otps', 'expired_sessions', 'recent_views', 'deliveries', 'read_notifications'):
        querysets[name].delete()
    querysets['callback_payloads'].update(payload={})
    return counts
