"""Request correlation IDs and lightweight sliding-window rate limits."""

from __future__ import annotations

import ipaddress
import logging
import time
import uuid
from contextlib import suppress
from contextvars import ContextVar

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

request_id_var: ContextVar[str] = ContextVar('request_id', default='-')


class RequestIdFilter(logging.Filter):
    """Inject the current request ID into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get('X-Request-ID') or uuid.uuid4().hex
        request.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response['X-Request-ID'] = rid
        return response


class SimpleRateLimitMiddleware:
    """
    Cache-backed rate limiter. Fail-open if cache errors.
    Limits selected path prefixes only.
    """

    LIMITS = (
        ('/account/login/', 20, 60),
        ('/account/register/', 10, 60),
        ('/account/verify/resend/', 3, 60),
        # Covers the whole reset flow (form → done → confirm → complete),
        # so the limit is sized for navigation, not just email POSTs.
        ('/account/password-reset/', 20, 60),
        ('/search/', 60, 60),
        ('/htmx/search/', 90, 60),
        ('/payments/callback/', 30, 60),
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        for prefix, limit, window in self.LIMITS:
            if path.startswith(prefix):
                if not self._allow(request, prefix, limit, window):
                    return HttpResponse('Too many requests. Try again shortly.', status=429)
                break
        return self.get_response(request)

    def _allow(self, request, prefix: str, limit: int, window: int) -> bool:
        remote_addr = request.META.get('REMOTE_ADDR', '')
        try:
            ip = str(ipaddress.ip_address(remote_addr))
        except ValueError:
            ip = 'unknown'

        trusted_proxies = getattr(settings, 'TRUSTED_PROXY_IPS', [])
        client_ip_header = getattr(settings, 'TRUSTED_CLIENT_IP_HEADER', '')
        if ip in trusted_proxies and client_ip_header:
            candidate = request.META.get(client_ip_header, '').strip()
            with suppress(ValueError):
                ip = str(ipaddress.ip_address(candidate))
        bucket = int(time.time() // window)
        key = f'rl:{prefix}:{ip}:{bucket}'
        try:
            if cache.add(key, 1, window + 1):
                return True
            return cache.incr(key) <= limit
        except Exception:
            logging.getLogger(__name__).exception('Rate-limit cache failure; allowing request')
            return True
