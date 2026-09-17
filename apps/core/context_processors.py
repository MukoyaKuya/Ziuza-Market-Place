from django.conf import settings


def site_flags(request):
    """Expose public-preview / payment honesty flags to templates."""
    return {
        "public_preview_mode": bool(getattr(settings, "PUBLIC_PREVIEW_MODE", False)),
        "payment_provider": getattr(settings, "PAYMENT_PROVIDER", "fake"),
    }
