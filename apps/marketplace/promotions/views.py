from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods, require_POST

from apps.marketplace.promotions.models import DiscountType, Promotion
from apps.marketplace.promotions.services import create_promotion, set_promotion_active
from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.permissions import MANAGE_PROMOTIONS, ensure_shop_permission
from apps.marketplace.shops.selectors import get_shop_for_user


@login_required
@require_http_methods(['GET', 'POST'])
def seller_promotions(request):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        return redirect('shops:onboarding')
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_PROMOTIONS)
    if request.method == 'POST':
        try:
            starts_at = parse_datetime(request.POST.get('starts_at') or '')
            ends_at = parse_datetime(request.POST.get('ends_at') or '')
            if starts_at and timezone.is_naive(starts_at):
                starts_at = timezone.make_aware(starts_at)
            if ends_at and timezone.is_naive(ends_at):
                ends_at = timezone.make_aware(ends_at)
            create_promotion(
                actor=request.user, shop=shop, name=request.POST.get('name') or '', code=request.POST.get('code') or '',
                discount_type=request.POST.get('discount_type') or '', value=Decimal(request.POST.get('value') or '0'),
                minimum_spend=Decimal(request.POST.get('minimum_spend') or '0'),
                usage_limit=int(request.POST['usage_limit']) if request.POST.get('usage_limit') else None,
                per_user_limit=int(request.POST.get('per_user_limit') or 1),
                starts_at=starts_at, ends_at=ends_at,
            )
        except (ValidationError, ValueError, InvalidOperation, TypeError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, 'Promotion created.')
            return redirect('promotions:seller_list')
    return render(request, 'promotions/seller_list.html', dashboard_context(
        actor=request.user, shop=shop, section='promotions',
        promotions=shop.promotions.all(), discount_types=DiscountType.choices,
    ))


@login_required
@require_POST
def toggle_promotion(request, promotion_id):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        raise Http404
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_PROMOTIONS)
    try:
        promotion = Promotion.objects.select_related('shop').get(id=promotion_id, shop=shop)
    except Promotion.DoesNotExist as exc:
        raise Http404 from exc
    set_promotion_active(actor=request.user, promotion=promotion, active=not promotion.is_active)
    return redirect('promotions:seller_list')
