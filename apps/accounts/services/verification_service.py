import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import EmailOTP, User
from apps.core.commerce_events import emit_commerce_event

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5


def _digest(*, otp_id, code: str) -> str:
    message = f'{otp_id}:{code}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def issue_email_otp(*, user: User) -> str | None:
    """Invalidate pending codes, issue a fresh 6-digit OTP, and queue the email.

    Returns the raw code, or None when the email is already verified. A signup
    must never fail because the email could not be sent; the user can always
    request a resend from the verification page.
    """
    if user.email_verified:
        return None
    EmailOTP.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=timezone.now())
    code = f'{secrets.randbelow(10**6):06d}'
    otp = EmailOTP(
        user=user,
        expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    otp.code_digest = _digest(otp_id=otp.id, code=code)
    otp.save()
    try:
        from apps.accounts.tasks import send_email_otp
        send_email_otp(user_id=user.id, code=code)
    except Exception:
        logger.exception('Failed to send verification code for %s', user.email)
    return code


@transaction.atomic
def verify_email_otp(*, user: User, code: str) -> bool:
    """Consume a verification code. Rate-limited per code to OTP_MAX_ATTEMPTS tries."""
    otp = EmailOTP.objects.filter(user=user, consumed_at__isnull=True).order_by('-created_at').first()
    if otp is None or otp.expires_at <= timezone.now():
        return False

    otp = EmailOTP.objects.select_for_update().get(pk=otp.pk)
    if otp.consumed_at:
        return False

    otp.attempts += 1
    digest_matches = secrets.compare_digest(
        otp.code_digest,
        _digest(otp_id=otp.id, code=(code or '').strip()),
    )
    if otp.attempts > OTP_MAX_ATTEMPTS or not digest_matches:
        otp.save(update_fields=['attempts'])
        return False

    otp.consumed_at = timezone.now()
    otp.save(update_fields=['consumed_at', 'attempts'])
    newly_verified = not user.email_verified
    if newly_verified:
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=['email_verified', 'email_verified_at', 'updated_at'])
        transaction.on_commit(lambda: emit_commerce_event(
            'onboarding.email_verified', user_id=user.id,
        ))
    return True
