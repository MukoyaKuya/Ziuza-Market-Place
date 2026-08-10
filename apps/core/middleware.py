"""Lightweight sliding-window rate limits for auth, search, and payment callbacks."""

from __future__ import annotations

import time
import logging

from django.conf import settings

from django.core.cache import cache
from django.http import HttpResponse


class SimpleRateLimitMiddleware:
    """
    Cache-backed rate limiter. Fail-open if cache errors.
    Limits selected path prefixes only.
    """

    LIMITS = (
        ('/account/login/', 20, 60),
        ('/account/register/', 10, 60),
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
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        if getattr(settings, 'TRUST_X_FORWARDED_FOR', False):
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
            if forwarded:
                ip = forwarded.split(',')[0].strip()
        bucket = int(time.time() // window)
        key = f'rl:{prefix}:{ip}:{bucket}'
        try:
            if cache.add(key, 1, window + 1):
                return True
            return cache.incr(key) <= limit
        except Exception:
            logging.getLogger(__name__).exception('Rate-limit cache failure; allowing request')
            return True
