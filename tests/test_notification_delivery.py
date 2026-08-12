from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.marketplace.notifications.delivery import deliver_pending_notifications
from apps.marketplace.notifications.models import (
    DeliveryStatus,
    DigestFrequency,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    notify,
)


User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def recipient(db):
    return User.objects.create_user(email='alerts@ziuza.co.ke', password=PASSWORD, display_name='Alerts')


@pytest.mark.django_db
def test_notification_is_durable_and_queues_immediate_email(recipient):
    notification = notify(
        recipient=recipient,
        type='order_placed',
        title='New order received',
        body='Order ZIU-123 awaits confirmation.',
        target_url='/seller/orders/123/',
    )

    delivery = NotificationDelivery.objects.get(notification=notification)
    assert Notification.objects.filter(id=notification.id).exists()
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.mode == DigestFrequency.IMMEDIATE
    assert delivery.recipient == recipient


@pytest.mark.django_db
def test_disabled_category_keeps_in_app_update_without_email(recipient):
    preference = NotificationPreference.objects.create(user=recipient, shipping_updates=False)

    notification = notify(
        recipient=recipient,
        type='shipment_update',
        title='Parcel shipped',
    )

    assert Notification.objects.filter(id=notification.id).exists()
    assert not NotificationDelivery.objects.filter(notification=notification).exists()
    assert preference.shipping_updates is False


@pytest.mark.django_db
def test_preferences_screen_cancels_already_pending_disabled_mail(client, recipient):
    notification = notify(recipient=recipient, type='message', title='New message')
    client.force_login(recipient)

    response = client.post(reverse('notifications:settings'), {
        'email_enabled': 'on',
        'digest_frequency': 'immediate',
        'order_updates': 'on',
        'shipping_updates': 'on',
        'marketplace_updates': 'on',
        'saved_searches': 'on',
        'inventory_updates': 'on',
    })

    assert response.status_code == 302
    delivery = NotificationDelivery.objects.get(notification=notification)
    assert delivery.status == DeliveryStatus.CANCELLED
    assert Notification.objects.filter(id=notification.id).exists()


@pytest.mark.django_db
def test_immediate_worker_sends_absolute_link_and_marks_delivery_sent(recipient):
    notification = notify(
        recipient=recipient,
        type='order_placed',
        title='Order ready',
        body='Your order is ready.',
        target_url='/account/orders/ZIU-1/',
    )

    result = deliver_pending_notifications()

    delivery = NotificationDelivery.objects.get(notification=notification)
    assert result == {'sent': 1, 'failed': 0}
    assert delivery.status == DeliveryStatus.SENT
    assert delivery.sent_at is not None
    assert len(mail.outbox) == 1
    assert 'http://localhost:8000/account/orders/ZIU-1/' in mail.outbox[0].body


@pytest.mark.django_db
def test_daily_updates_are_combined_into_one_digest(recipient):
    NotificationPreference.objects.create(user=recipient, digest_frequency=DigestFrequency.DAILY)
    first = notify(recipient=recipient, type='message', title='First conversation')
    second = notify(recipient=recipient, type='order_placed', title='Second order')
    NotificationDelivery.objects.filter(notification__in=[first, second]).update(available_at=timezone.now())

    result = deliver_pending_notifications()

    assert result == {'sent': 2, 'failed': 0}
    assert len(mail.outbox) == 1
    assert 'First conversation' in mail.outbox[0].body
    assert 'Second order' in mail.outbox[0].body
    assert NotificationDelivery.objects.filter(status=DeliveryStatus.SENT).count() == 2


@pytest.mark.django_db
def test_temporary_email_failure_is_retried_with_backoff(monkeypatch, recipient):
    notification = notify(recipient=recipient, type='order_placed', title='Retry me')

    def fail_send(*args, **kwargs):
        raise ConnectionError('temporary mail provider failure')

    monkeypatch.setattr('apps.marketplace.notifications.delivery.send_mail', fail_send)
    before = timezone.now()
    result = deliver_pending_notifications()

    delivery = NotificationDelivery.objects.get(notification=notification)
    assert result == {'sent': 0, 'failed': 1}
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.attempts == 1
    assert delivery.available_at >= before + timedelta(minutes=4)
    assert 'temporary mail provider failure' in delivery.last_error


@pytest.mark.django_db
def test_never_email_preference_does_not_create_delivery(recipient):
    NotificationPreference.objects.create(
        user=recipient,
        email_enabled=True,
        digest_frequency=DigestFrequency.NEVER,
    )

    notification = notify(recipient=recipient, type='moderation', title='Account update')

    assert Notification.objects.filter(id=notification.id).exists()
    assert not NotificationDelivery.objects.filter(notification=notification).exists()


@pytest.mark.django_db
def test_unread_count_partial(client, recipient):
    notify(recipient=recipient, type='order_placed', title='Unread 1')
    client.force_login(recipient)
    response = client.get(reverse('notifications:unread_count'))
    assert response.status_code == 200
    assert 'Unread 1' not in response.content.decode()  # Body isn't rendered in badge
    assert '1' in response.content.decode()

