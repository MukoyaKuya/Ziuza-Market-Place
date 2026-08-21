"""Cache-busting version tags for static assets."""

import time
from pathlib import Path

from django import template
from django.conf import settings

register = template.Library()

_STATIC_VERSION_CACHE: dict[str, str] = {}


def _file_version(path: Path) -> str:
    """Last-modified stamp for cache-busting static assets; stable per process."""
    key = str(path)
    if key not in _STATIC_VERSION_CACHE:
        try:
            _STATIC_VERSION_CACHE[key] = str(int(path.stat().st_mtime))
        except OSError:
            _STATIC_VERSION_CACHE[key] = '0'
    return _STATIC_VERSION_CACHE[key]


@register.simple_tag
def asset_version(path: str) -> str:
    """Return a version string for a static file, for `?v=` cache busting."""
    if settings.DEBUG:
        return str(int(time.time()))
    if settings.STATIC_ROOT:
        return _file_version(Path(settings.STATIC_ROOT) / path.lstrip('/'))
    return _file_version(Path(settings.BASE_DIR) / 'static' / path.lstrip('/'))
