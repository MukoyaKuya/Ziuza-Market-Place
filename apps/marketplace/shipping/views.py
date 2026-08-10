from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.views.decorators.http import require_http_methods, require_POST

from apps.marketplace.orders.models import SellerOrder
from apps.marketplace.shipping.forms import ShippingProfileForm
from apps.marketplace.shipping.models import ShippingProfile, update_seller_fulfillment
from apps.marketplace.shipping.services import delete_shipping_profile, save_shipping_profile
from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.selectors import get_shop_for_user
from apps.marketplace.shops.permissions import MANAGE_ORDERS, MANAGE_SHIPPING, ensure_shop_permission


@login_required
@require_http_methods(['GET', 'POST'])
def shipping_profiles(request):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        return redirect('shops:onboarding')
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_SHIPPING)
    edit_profile = None
    if request.method == 'GET' and request.GET.get('edit'):
        edit_profile = ShippingProfile.objects.filter(id=request.GET['edit'], shop=shop).first()
        if edit_profile is None:
            raise Http404('Shipping profile not found.')
    form = ShippingProfileForm(instance=edit_profile)
    if request.method == 'POST':
        action = request.POST.get('action')
        profile = None
        if request.POST.get('profile_id'):
            profile = ShippingProfile.objects.filter(id=request.POST['profile_id'], shop=shop).first()
            if profile is None:
                raise Http404('Shipping profile not found.')
        if action == 'delete':
            if profile is None:
                raise Http404('Shipping profile not found.')
            delete_shipping_profile(actor=request.user, shop=shop, profile=profile)
            messages.success(request, 'Shipping profile removed. Listings using it now use marketplace delivery methods.')
            return redirect('shipping:profiles')
        form = ShippingProfileForm(request.POST, instance=profile)
        if form.is_valid():
            try:
                save_shipping_profile(actor=request.user, shop=shop, profile=profile, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Shipping profile saved.')
                return redirect('shipping:profiles')
    return render(request, 'shipping/seller/profiles.html', dashboard_context(actor=request.user,
        shop=shop,
        section='shipping',
        form=form,
        profiles=shop.shipping_profiles.prefetch_related('listings').all(),
    ))


@login_required
@require_POST
def seller_update_fulfillment(request, seller_order_id):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        raise Http404
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_ORDERS)
    try:
        seller_order = SellerOrder.objects.select_related('order', 'shop').get(id=seller_order_id, shop=shop)
    except SellerOrder.DoesNotExist as exc:
        raise Http404 from exc
    try:
        update_seller_fulfillment(
            actor=request.user,
            seller_order=seller_order,
            status=request.POST.get('status'),
            tracking_number=request.POST.get('tracking_number') or '',
            carrier=request.POST.get('carrier') or '',
            note=request.POST.get('note') or '',
        )
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, 'Fulfillment updated and the buyer was notified.')
    return redirect('orders:seller_detail', seller_order_id=seller_order.id)
