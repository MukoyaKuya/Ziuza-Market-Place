import json
import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from apps.marketplace.orders.models import Order
from apps.marketplace.payments.providers import get_provider


def _callback_data(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    return request.POST


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
        payment = order.payments.filter(provider='mpesa', status='pending').order_by('-initiated_at').first()
        if request.method == 'POST':
            try:
                payment = provider.initiate_payment(
                    order=order,
                    phone=request.POST.get('phone') or getattr(request.user, 'phone', '') or '',
                )
            except Exception as exc:
                messages.error(request, str(exc))
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
    payment = provider.initiate_payment(order=order)
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
    try:
        payment = provider.process_callback(payload=payload)
    except Exception:
        logging.getLogger(__name__).exception('fake_callback failed')
        return JsonResponse({'ok': False, 'error': 'callback_rejected'}, status=400)
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
    try:
        payment = provider.process_callback(payload=payload)
    except Exception:
        logging.getLogger(__name__).exception('mpesa_callback failed')
        return JsonResponse({'ok': False, 'error': 'callback_rejected'}, status=400)
    return JsonResponse({'ok': True, 'status': payment.status, 'order': payment.order.public_number})


@login_required
@require_POST
def fake_confirm(request, public_number):
    """Buyer-triggered confirm that still goes through provider callback verification."""
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
    if getattr(settings, 'MPESA_LIVE', False):
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
