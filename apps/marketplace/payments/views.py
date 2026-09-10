import json
import logging
import secrets
from decimal import InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from apps.marketplace.orders.models import Order, SellerOrder
from apps.marketplace.payments.models import CallbackOutcome, Payment, PaymentCallbackEvent, PaymentStatusChoice
from apps.marketplace.payments.providers import get_provider
from apps.marketplace.payments.whatsapp import confirm_whatsapp_payment
from apps.marketplace.shops.permissions import MANAGE_ORDERS, ensure_shop_permission
from apps.marketplace.shops.selectors import get_shop_for_user

CALLBACK_ERRORS = (ValidationError, ValueError, Payment.DoesNotExist, InvalidOperation)


def _callback_data(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    return request.POST


def _start_callback_event(*, provider: str, payload: dict) -> PaymentCallbackEvent:
    reference = payload.get('provider_reference') or payload.get('CheckoutRequestID') or ''
    return PaymentCallbackEvent.objects.create(
        provider=provider,
        provider_reference=reference,
        authenticated=bool(payload.get('callback_authenticated')),
        payload=payload,
    )


def _finish_callback_event(*, event: PaymentCallbackEvent, outcome: str, payment: Payment | None = None, error_code: str = '') -> None:
    event.payment = payment
    event.outcome = outcome
    event.error_code = error_code
    event.processed_at = timezone.now()
    event.save(update_fields=['payment', 'outcome', 'error_code', 'processed_at'])


@login_required
@require_http_methods(['GET', 'POST'])
def initiate_payment(request, public_number):
    try:
        order = Order.objects.get(public_number=public_number, buyer=request.user)
    except Order.DoesNotExist as exc:
        raise Http404 from exc
    provider_code = getattr(settings, 'PAYMENT_PROVIDER', 'fake')
    provider = get_provider(provider_code)
    if provider.code == 'mpesa':
        payment = (
            order.payments.filter(
                provider='mpesa',
                status__in=[PaymentStatusChoice.INITIATED, PaymentStatusChoice.PENDING],
            )
            .order_by('-initiated_at')
            .first()
        )
        if request.method == 'POST':
            try:
                payment = provider.initiate_payment(
                    order=order,
                    phone=request.POST.get('phone') or getattr(request.user, 'phone', '') or '',
                )
            except Exception as exc:
                messages.error(request, str(exc))
                payment = (
                    order.payments.filter(
                        provider='mpesa',
                        status__in=[PaymentStatusChoice.INITIATED, PaymentStatusChoice.PENDING],
                    )
                    .order_by('-initiated_at')
                    .first()
                )
        return render(
            request,
            'payments/mpesa_initiate.html',
            {
                'order': order,
                'payment': payment,
                'provider_code': provider.code,
                'daraja_enabled': getattr(settings, 'MPESA_DARAJA_ENABLED', False),
                'page_title': 'Pay for order',
            },
        )
    payment = provider.initiate_payment(order=order, phone='')
    template = 'payments/mpesa_initiate.html' if provider.code == 'mpesa' else 'payments/initiate.html'
    return render(
        request,
        template,
        {
            'order': order,
            'payment': payment,
            'provider_code': provider.code,
            'page_title': 'Pay for order',
        },
    )


@csrf_exempt
@require_POST
def fake_callback(request):
    """Sandbox callback — verify reference/amount server-side (idempotent)."""
    if not settings.DEBUG:
        raise Http404()
    data = _callback_data(request)
    payload = {
        'provider_reference': data.get('provider_reference'),
        'amount': data.get('amount'),
        'currency': data.get('currency', 'KES'),
    }
    provider = get_provider('fake')
    event = _start_callback_event(provider='fake', payload=payload)
    try:
        payment = provider.process_callback(payload=payload)
    except CALLBACK_ERRORS as exc:
        _finish_callback_event(event=event, outcome=CallbackOutcome.REJECTED, error_code=type(exc).__name__)
        logging.getLogger(__name__).exception('fake_callback failed')
        return JsonResponse({'ok': False, 'error': 'callback_rejected'}, status=400)
    _finish_callback_event(event=event, outcome=CallbackOutcome.PROCESSED, payment=payment)
    return JsonResponse({'ok': True, 'status': payment.status, 'order': payment.order.public_number})


@csrf_exempt
@require_POST
def mpesa_callback(request):
    """
    STK callback endpoint. Accepts form or JSON-like POST fields for the scaffold.
    Always verifies amount + CheckoutRequestID; optional HMAC when secret set.
    """
    data = _callback_data(request)
    callback = data.get('Body', {}).get('stkCallback', {}) if isinstance(data, dict) else {}
    source = callback or data
    metadata = source.get('CallbackMetadata', {}).get('Item', []) if isinstance(source, dict) else []
    metadata_values = {item.get('Name'): item.get('Value') for item in metadata if isinstance(item, dict)}
    reference = source.get('CheckoutRequestID') or source.get('provider_reference')
    payload = {
        'provider_reference': reference,
        'CheckoutRequestID': reference,
        'amount': source.get('amount') or source.get('Amount') or metadata_values.get('Amount'),
        'currency': source.get('currency', 'KES'),
        'ResultCode': source.get('ResultCode', '0'),
        'callback_authenticated': bool(settings.MPESA_CALLBACK_SECRET) and secrets.compare_digest(
            settings.MPESA_CALLBACK_SECRET,
            request.headers.get('X-Mpesa-Callback-Token', '') or request.GET.get('token', ''),
        ),
    }
    provider = get_provider('mpesa')
    event = _start_callback_event(provider='mpesa', payload=payload)
    try:
        payment = provider.process_callback(payload=payload)
    except CALLBACK_ERRORS as exc:
        _finish_callback_event(event=event, outcome=CallbackOutcome.REJECTED, error_code=type(exc).__name__)
        logging.getLogger(__name__).exception('mpesa_callback failed')
        return JsonResponse({'ok': False, 'error': 'callback_rejected'}, status=400)
    _finish_callback_event(event=event, outcome=CallbackOutcome.PROCESSED, payment=payment)
    return JsonResponse({'ok': True, 'status': payment.status, 'order': payment.order.public_number})


@login_required
@require_POST
def seller_confirm_whatsapp(request, seller_order_id):
    """Seller confirms the WhatsApp-arranged payment actually arrived (M-Pesa/cash)."""
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        raise Http404
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_ORDERS)
    try:
        seller_order = SellerOrder.objects.select_related('order').get(id=seller_order_id, shop=shop)
    except SellerOrder.DoesNotExist as exc:
        raise Http404 from exc
    try:
        confirm_whatsapp_payment(actor=request.user, seller_order=seller_order)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('orders:seller_detail', seller_order_id=seller_order_id)
    messages.success(request, 'Payment marked as received — the buyer has been notified.')
    return redirect('orders:seller_detail', seller_order_id=seller_order_id)


@login_required
@require_POST
def fake_confirm(request, public_number):
    """Buyer-triggered confirm that still goes through provider callback verification."""
    if not settings.DEBUG or getattr(settings, 'PAYMENT_PROVIDER', '') != 'fake':
        raise Http404
    try:
        order = Order.objects.get(public_number=public_number, buyer=request.user)
        payment = order.payments.filter(provider='fake').latest('initiated_at')
    except Exception as exc:
        raise Http404 from exc
    provider = get_provider('fake')
    provider.process_callback(
        payload={
            'provider_reference': payment.provider_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
        }
    )
    messages.success(request, 'Payment confirmed.')
    return redirect('orders:buyer_detail', public_number=order.public_number)


@login_required
@require_POST
def mpesa_sandbox_confirm(request, public_number):
    """Dev-only confirm for M-Pesa scaffold when Daraja is not connected."""
    if (
        not settings.DEBUG
        or getattr(settings, 'PAYMENT_PROVIDER', '') != 'mpesa'
        or getattr(settings, 'MPESA_LIVE', False)
    ):
        raise Http404
    try:
        order = Order.objects.get(public_number=public_number, buyer=request.user)
        payment = order.payments.filter(provider='mpesa').latest('initiated_at')
    except Exception as exc:
        raise Http404 from exc
    provider = get_provider('mpesa')
    provider.process_callback(
        payload={
            'provider_reference': payment.provider_reference,
            'CheckoutRequestID': payment.provider_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'ResultCode': '0',
        }
    )
    messages.success(request, 'M-Pesa payment confirmed (sandbox).')
    return redirect('orders:buyer_detail', public_number=order.public_number)
