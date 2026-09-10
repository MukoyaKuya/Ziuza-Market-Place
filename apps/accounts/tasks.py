import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.services.verification_service import OTP_TTL_MINUTES

logger = logging.getLogger(__name__)


@shared_task
def send_email_otp_task(*, user_id, code: str) -> None:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('Verification code email skipped — user %s no longer exists.', user_id)
        return

    send_mail(
        subject='Your Ziuza verification code',
        message=(
            f'Hi {user.get_full_name()},\n\n'
            f'Your Ziuza verification code is: {code}\n\n'
            f'It expires in {OTP_TTL_MINUTES} minutes. Enter it in the browser tab where you '
            'are creating your account. If you did not create a Ziuza account, you can ignore '
            'this email.\n\n'
            '— The Ziuza Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_email_otp(*, user_id, code: str) -> None:
    """Queue the transactional email; fall back to a synchronous send when no broker is reachable."""
    try:
        send_email_otp_task.delay(user_id=user_id, code=code)
    except Exception:
        logger.exception('Could not queue verification code email — sending synchronously instead.')
        send_email_otp_task(user_id=user_id, code=code)
