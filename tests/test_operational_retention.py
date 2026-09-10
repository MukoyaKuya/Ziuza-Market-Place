from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import EmailOTP
from apps.core.retention import purge_operational_data
from apps.marketplace.payments.models import PaymentCallbackEvent

User = get_user_model()


@pytest.mark.django_db
def test_operational_retention_reports_without_changing_data():
    user = User.objects.create_user(email='retention@ziuza.co.ke', password='Password123!')
    otp = EmailOTP.objects.create(
        user=user,
        code_digest='a' * 64,
        expires_at=timezone.now() - timedelta(days=2),
    )
    event = PaymentCallbackEvent.objects.create(
        provider='mpesa',
        provider_reference='old-callback',
        payload={'amount': '100'},
    )
    PaymentCallbackEvent.objects.filter(pk=event.pk).update(received_at=timezone.now() - timedelta(days=366))

    counts = purge_operational_data()

    assert counts['email_otps'] == 1
    assert counts['callback_payloads'] == 1
    assert EmailOTP.objects.filter(pk=otp.pk).exists()
    event.refresh_from_db()
    assert event.payload == {'amount': '100'}


@pytest.mark.django_db
def test_operational_retention_executes_deletion_and_callback_redaction():
    user = User.objects.create_user(email='retention-execute@ziuza.co.ke', password='Password123!')
    otp = EmailOTP.objects.create(
        user=user,
        code_digest='b' * 64,
        expires_at=timezone.now() - timedelta(days=2),
    )
    event = PaymentCallbackEvent.objects.create(
        provider='mpesa',
        provider_reference='redacted-callback',
        payload={'phone': '254700000000'},
    )
    PaymentCallbackEvent.objects.filter(pk=event.pk).update(received_at=timezone.now() - timedelta(days=366))

    purge_operational_data(execute=True)

    assert not EmailOTP.objects.filter(pk=otp.pk).exists()
    event.refresh_from_db()
    assert event.payload == {}
