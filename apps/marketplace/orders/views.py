import logging
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import Address
from apps.accounts.selectors import list_addresses_for_user
from apps.marketplace.cart.services import annotate_cart_totals, get_or_create_cart
from apps.marketplace.orders.models import (
    DownloadGrant,
    HelpRequest,
    HelpRequestReason,
    Order,
    ProtectionCaseEvidence,
    ProtectionCaseType,
    RequestedOutcome,
    SellerOrder,
)
from apps.marketplace.orders.services import cancel_order, create_checkout_order
from apps.marketplace.orders.support import (
    add_case_evidence,
    add_case_message,
    can_access_case,
    escalate_help_request,
    open_help_request,
    seller_respond_to_help_request,
)
from apps.marketplace.shipping.services import calculate_shipping_quotes
from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.permissions import (
    MANAGE_ORDERS,
    MANAGE_SUPPORT,
    VIEW_ORDERS,
    ensure_shop_permission,
    user_has_shop_permission,
)
from apps.marketplace.shops.selectors import get_shop_for_user


@login_required
@require_http_methods(['GET', 'POST'])
def checkout(request):
    cart = get_or_create_cart(request=request)
    totals = annotate_cart_totals(cart)
    requires_shipping = any(line['item'].listing.product_type != 'digital' for line in totals['lines'])
    addresses = list_addresses_for_user(user=request.user)
    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        method_code = request.POST.get('shipping_method') or 'standard'
        try:
            address = Address.objects.get(id=address_id, user=request.user) if requires_shipping and address_id else None
            methods = calculate_shipping_quotes(
                lines=totals['lines'], county=address.county if address else ''
            ) if requires_shipping else []
            method = next((item for item in methods if item.code == method_code), None) if requires_shipping else None
            if requires_shipping:
                if method is None:
                    raise ValidationError('Selected shipping method is not available for this address.')
                if not method.is_pickup and address is None:
                    raise ValidationError('Choose a shipping address for delivery.')
            order = create_checkout_order(
                actor=request.user,
                cart=cart,
                shipping_address=address,
                shipping_method_code=method.code if method else 'digital',
                shipping_fee=method.base_fee if method else Decimal('0.00'),
                shipping_breakdown=method.breakdown if method else [],
                coupon_code=request.POST.get('coupon_code') or '',
            )
            # notify seller(s)
            try:
                from apps.marketplace.notifications.services import notify

                for seller_order in order.seller_orders.select_related('shop__owner'):
                    notify(
                        recipient=seller_order.shop.owner,
                        type='order_placed',
                        title='New order received',
                        body=f'Order {order.public_number} awaits payment confirmation.',
                        target_url=f'/seller/orders/{seller_order.id}/',
                    )
            except Exception:
                logging.getLogger(__name__).exception(
                    'Order created but seller notification failed',
                    extra={'order_public_number': order.public_number},
                )
            return redirect('payments:initiate', public_number=order.public_number)
        except (Address.DoesNotExist, ValidationError) as exc:
            messages.error(request, str(exc) or 'Checkout failed.')

    quote_address = addresses.filter(is_default_shipping=True).first() or addresses.first()
    shipping_quotes = calculate_shipping_quotes(
        lines=totals['lines'], county=quote_address.county if quote_address else ''
    ) if requires_shipping else []
    if requires_shipping and quote_address is None:
        shipping_quotes = [quote for quote in shipping_quotes if quote.is_pickup]
    return render(
        request,
        'orders/checkout.html',
        {
            **totals,
            'addresses': addresses,
            'page_title': 'Checkout',
            'shipping_methods': shipping_quotes,
            'requires_shipping': requires_shipping,
            'allows_addressless_pickup': any(quote.is_pickup for quote in shipping_quotes),
        },
    )


@login_required
def buyer_orders(request):
    orders = Order.objects.filter(buyer=request.user).prefetch_related('items')
    return render(
        request,
        'orders/buyer_list.html',
        {'orders': orders, 'page_title': 'Orders', 'account_section': 'orders'},
    )


@login_required
def buyer_order_detail(request, public_number):
    try:
        order = Order.objects.prefetch_related('items', 'seller_orders__shop', 'seller_orders__shipments__events').get(
            public_number=public_number, buyer=request.user
        )
    except Order.DoesNotExist as exc:
        raise Http404 from exc
    if order.payment_status == 'paid':
        from apps.marketplace.listings.models import DigitalAsset
        grants = {grant.order_item_id: grant for grant in DownloadGrant.objects.filter(order_item__order=order, buyer=request.user)}
        for item in order.items.all():
            grant = grants.get(item.id)
            item.secure_download_grant = grant
            item.download_assets = (
                list(DigitalAsset.objects.filter(listing_id=item.listing_id, is_active=True))
                if grant and item.listing_id
                else []
            )
    return render(request, 'orders/buyer_detail.html', {'order': order, 'page_title': order.public_number})


@login_required
@require_POST
def buyer_order_cancel(request, public_number):
    try:
        order = Order.objects.get(public_number=public_number, buyer=request.user)
        cancel_order(actor=request.user, order=order)
        messages.success(request, 'Order cancelled and reserved stock released.')
    except Order.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('orders:buyer_detail', public_number=public_number)


@login_required
def seller_orders(request):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        return redirect('shops:onboarding')
    ensure_shop_permission(actor=request.user, shop=shop, permission=VIEW_ORDERS)
    orders = (
        SellerOrder.objects.filter(shop=shop)
        .select_related('order')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    return render(
        request,
        'orders/seller_list.html',
        dashboard_context(actor=request.user, shop=shop, section='orders', seller_orders=orders),
    )


@login_required
def seller_order_detail(request, seller_order_id):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        return redirect('shops:onboarding')
    ensure_shop_permission(actor=request.user, shop=shop, permission=VIEW_ORDERS)
    try:
        seller_order = SellerOrder.objects.prefetch_related(
            'items', 'shipments__events', 'help_requests__messages__author',
            'help_requests__evidence__uploaded_by', 'help_requests__events__actor',
        ).select_related('order').get(
            id=seller_order_id, shop=shop
        )
    except SellerOrder.DoesNotExist as exc:
        raise Http404 from exc
    shipping_breakdown = [
        item for item in seller_order.order.shipping_breakdown
        if item.get('shop_id') == str(shop.id)
    ]
    return render(
        request,
        'orders/seller_detail.html',
        dashboard_context(
            actor=request.user, shop=shop, section='orders', seller_order=seller_order,
            shipping_breakdown=shipping_breakdown,
            can_manage_orders=user_has_shop_permission(actor=request.user, shop=shop, permission=MANAGE_ORDERS),
            can_manage_support=user_has_shop_permission(actor=request.user, shop=shop, permission=MANAGE_SUPPORT),
        ),
    )


@login_required
@require_http_methods(['GET', 'POST'])
def buyer_help_create(request, seller_order_id):
    try:
        seller_order = SellerOrder.objects.select_related('order', 'shop').get(id=seller_order_id, order__buyer=request.user)
    except SellerOrder.DoesNotExist as exc:
        raise Http404 from exc
    if request.method == 'POST':
        try:
            case = open_help_request(
                actor=request.user,
                seller_order=seller_order,
                reason=request.POST.get('reason') or '',
                description=request.POST.get('description') or '',
                desired_resolution=request.POST.get('desired_resolution') or '',
                case_type=request.POST.get('case_type') or ProtectionCaseType.SUPPORT,
                requested_outcome=request.POST.get('requested_outcome') or '',
            )
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(request, 'Your help request was sent to the seller.')
            return redirect('orders:buyer_help_detail', case_id=case.id)
    return render(request, 'orders/help_create.html', {
        'seller_order': seller_order, 'reasons': HelpRequestReason.choices,
        'case_types': ProtectionCaseType.choices, 'requested_outcomes': RequestedOutcome.choices,
        'page_title': 'Get help with order',
    })


@login_required
def buyer_help_detail(request, case_id):
    try:
        case = HelpRequest.objects.select_related('order', 'seller_order__shop').prefetch_related(
            'messages__author', 'evidence__uploaded_by', 'events__actor',
        ).get(id=case_id, buyer=request.user)
    except HelpRequest.DoesNotExist as exc:
        raise Http404 from exc
    return render(request, 'orders/help_detail.html', {'case': case, 'page_title': 'Help request'})


@login_required
@require_POST
def buyer_help_escalate(request, case_id):
    try:
        case = HelpRequest.objects.get(id=case_id, buyer=request.user)
        escalate_help_request(actor=request.user, case=case)
        messages.success(request, 'Request escalated to Ziuza support.')
    except HelpRequest.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('orders:buyer_help_detail', case_id=case_id)


@login_required
@require_POST
def seller_help_respond(request, case_id):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        raise Http404
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_SUPPORT)
    try:
        case = HelpRequest.objects.select_related('seller_order__shop').get(id=case_id, seller_order__shop=shop)
        seller_respond_to_help_request(actor=request.user, case=case, response=request.POST.get('response') or '')
        messages.success(request, 'Response sent to the buyer.')
    except HelpRequest.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('orders:seller_detail', seller_order_id=case.seller_order_id)


@login_required
@require_POST
def protection_case_message(request, case_id):
    try:
        case = HelpRequest.objects.select_related('seller_order__shop').get(id=case_id)
        add_case_message(actor=request.user, case=case, body=request.POST.get('body') or '')
        messages.success(request, 'Message added to the case.')
    except HelpRequest.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    if case.buyer_id == request.user.id:
        return redirect('orders:buyer_help_detail', case_id=case.id)
    return redirect('orders:seller_detail', seller_order_id=case.seller_order_id)


@login_required
@require_POST
def protection_case_evidence(request, case_id):
    try:
        case = HelpRequest.objects.select_related('seller_order__shop').get(id=case_id)
        add_case_evidence(
            actor=request.user, case=case, uploaded_file=request.FILES.get('evidence'),
            description=request.POST.get('description') or '',
        )
        messages.success(request, 'Evidence added securely.')
    except HelpRequest.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    if case.buyer_id == request.user.id:
        return redirect('orders:buyer_help_detail', case_id=case.id)
    return redirect('orders:seller_detail', seller_order_id=case.seller_order_id)


@login_required
def protection_case_evidence_download(request, evidence_id):
    try:
        evidence = ProtectionCaseEvidence.objects.select_related(
            'case__seller_order__shop', 'case__buyer'
        ).get(id=evidence_id)
    except ProtectionCaseEvidence.DoesNotExist as exc:
        raise Http404 from exc
    if not can_access_case(actor=request.user, case=evidence.case):
        raise Http404
    response = FileResponse(
        evidence.file.open('rb'), as_attachment=True,
        filename=Path(evidence.original_name).name, content_type=evidence.content_type,
    )
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def download_digital_asset(request, grant_id, asset_id):
    from apps.marketplace.listings.models import DigitalAsset
    try:
        grant = DownloadGrant.objects.select_related('order_item__order').get(
            id=grant_id, buyer=request.user, is_active=True, order_item__order__payment_status='paid'
        )
        order_item = grant.order_item
        if not order_item.listing_id:
            raise Http404
        asset = DigitalAsset.objects.get(id=asset_id, listing_id=order_item.listing_id, is_active=True)
    except (DownloadGrant.DoesNotExist, DigitalAsset.DoesNotExist) as exc:
        raise Http404 from exc
    file_name = asset.file.name
    if not file_name:
        raise Http404
    DownloadGrant.objects.filter(pk=grant.pk).update(
        download_count=F('download_count') + 1,
        last_downloaded_at=timezone.now(),
    )
    filename = Path(file_name).name
    if getattr(settings, 'USE_X_ACCEL_REDIRECT', False):
        prefix = getattr(settings, 'X_ACCEL_REDIRECT_PREFIX', '/protected_media/').rstrip('/')
        response = HttpResponse(content_type='application/octet-stream')
        response['X-Accel-Redirect'] = f'{prefix}/{file_name}'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return FileResponse(asset.file.open('rb'), as_attachment=True, filename=filename)


@login_required
def buyer_order_status_partial(request, public_number):
    try:
        order = Order.objects.get(public_number=public_number, buyer=request.user)
    except Order.DoesNotExist as exc:
        raise Http404 from exc
    return render(
        request,
        'orders/partials/status_header.html',
        {'order': order},
    )

