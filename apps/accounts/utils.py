from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme


def email_verification_required(user) -> bool:
    return (
        getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', True)
        and not user.is_staff
        and not user.email_verified
    )


def safe_next_url(request, candidate, fallback):
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback
