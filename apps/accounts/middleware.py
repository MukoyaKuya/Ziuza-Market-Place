from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from apps.accounts.utils import email_verification_required

PENDING_VERIFICATION_SESSION_KEY = 'pending_verification_user_id'


class RequireVerifiedEmailMiddleware:
    """Keep unverified accounts behind the OTP gate, including old sessions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and email_verification_required(user)
        ):
            allowed_paths = {
                reverse('accounts:verify_email_otp'),
                reverse('accounts:resend_verification'),
                reverse('accounts:logout'),
            }
            static_url = settings.STATIC_URL
            media_url = settings.MEDIA_URL
            is_asset = request.path_info.startswith((static_url, media_url))
            if request.path_info not in allowed_paths and not is_asset:
                request.session[PENDING_VERIFICATION_SESSION_KEY] = str(user.id)
                return redirect('accounts:verify_email_otp')

        return self.get_response(request)
