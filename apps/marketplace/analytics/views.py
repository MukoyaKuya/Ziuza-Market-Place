from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.marketplace.analytics.selectors import ALLOWED_ANALYTICS_DAYS, shop_analytics_summary
from apps.marketplace.analytics.services import ensure_shop_metrics, nairobi_today
from datetime import timedelta

from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.selectors import get_shop_for_user
from apps.marketplace.shops.permissions import VIEW_ANALYTICS, ensure_shop_permission


@login_required
def seller_analytics(request):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        return redirect('shops:onboarding')
    ensure_shop_permission(actor=request.user, shop=shop, permission=VIEW_ANALYTICS)

    try:
        days = int(request.GET.get('days', 14))
    except (TypeError, ValueError):
        days = 14
    if days not in ALLOWED_ANALYTICS_DAYS:
        days = 14

    end = nairobi_today()
    start = end - timedelta(days=days - 1)
    ensure_shop_metrics(shop=shop, start=start, end=end)

    summary = shop_analytics_summary(shop=shop, days=days)
    return render(
        request,
        'analytics/seller.html',
        dashboard_context(actor=request.user, shop=shop, section='analytics', **summary),
    )
