from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_url(request, candidate, fallback):
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback
