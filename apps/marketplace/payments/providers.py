"""Payment provider abstractions. Business verification stays server-side."""

from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.commerce_events import emit_commerce_event
from apps.marketplace.orders.models import Order, PaymentStatus
from apps.marketplace.orders.services import mark_order_paid, release_order_inventory
from apps.marketplace.payments.daraja import DarajaClient, DarajaConfig
from apps.marketplace.payments.models import Payment, PaymentStatusChoice

logger = logging.getLogger(__name__)


class PaymentProvider:
    code = 'base'

    def initiate_payment(self, *, order: Order, phone: str = '') -> Payment:
        raise NotImplementedError

    def process_callback(self, *, payload: dict) -> Payment:
        raise NotImplementedError


def _ensure_payable_order(*, order: Order) -> None:
    if order.reservation_released_at:
        raise ValidationError('Order inventory reservation has been released.')
    if order.reservation_expires_at and order.reservation_expires_at <= timezone.now():
        release_order_inventory(order=order, payment_status=PaymentStatus.CANCELLED)
        raise ValidationError('Order inventory reservation has expired.')
    if order.payment_status not in {PaymentStatus.PENDING, PaymentStatus.PROCESSING}:
        raise ValidationError('Order cannot be paid from its current state.')


def _confirm_payment(*, payment: Payment, payload: dict) -> Payment:
    payment.status = PaymentStatusChoice.CONFIRMED
    payment.confirmed_at = timezone.now()
    payment.raw_metadata = {**payment.raw_metadata, 'callback': payload}
    payment.save()
    mark_order_paid(order=payment.order)
    transaction.on_commit(lambda: emit_commerce_event(
        'payment.confirmed',
        payment_id=payment.id,
        order_id=payment.order_id,
        provider=payment.provider,
        amount=payment.amount,
        currency=payment.currency,
    ))
    return payment


def _fail_payment(*, payment: Payment, reason: str, payload: dict) -> Payment:
    payment.status = PaymentStatusChoice.FAILED
    payment.raw_metadata = {**payment.raw_metadata, 'error': reason, 'callback': payload}
    payment.save()
    payment.order.payment_status = PaymentStatus.FAILED
    release_order_inventory(order=payment.order, payment_status=PaymentStatus.FAILED)
    transaction.on_commit(lambda: emit_commerce_event(
        'payment.failed',
        payment_id=payment.id,
        order_id=payment.order_id,
        provider=payment.provider,
        reason=reason,
    ))
    return payment


class FakePaymentProvider(PaymentProvider):
    code = 'fake'

    @transaction.atomic
    def initiate_payment(self, *, order: Order, phone: str = '') -> Payment:
        _ensure_payable_order(order=order)
        existing = (
            Payment.objects.filter(order=order, provider=self.code, status=PaymentStatusChoice.PENDING)
            .order_by('-initiated_at')
            .first()
        )
        if existing:
            return existing
        order.payment_status = PaymentStatus.PROCESSING
        order.save(update_fields=['payment_status', 'updated_at'])
        return Payment.objects.create(
            order=order,
            provider=self.code,
            provider_reference=f'FAKE-{order.public_number}-{secrets.token_hex(4)}',
            amount=order.grand_total,
            currency=order.currency,
            status=PaymentStatusChoice.PENDING,
            raw_metadata={'sandbox': True},
        )

    @transaction.atomic
    def process_callback(self, *, payload: dict) -> Payment:
        reference = payload.get('provider_reference')
        payment = Payment.objects.select_for_update().select_related('order').get(provider_reference=reference)
        if payment.provider != self.code:
            raise ValidationError('Payment provider mismatch.')
        if payment.status == PaymentStatusChoice.CONFIRMED:
            return payment
        if payload.get('amount') is None:
            return _fail_payment(payment=payment, reason='amount_missing', payload=payload)
        amount = Decimal(str(payload['amount']))
        if amount != payment.amount or payload.get('currency', payment.currency) != payment.currency:
            return _fail_payment(payment=payment, reason='amount_mismatch', payload=payload)
        return _confirm_payment(payment=payment, payload=payload)


class MpesaPaymentProvider(PaymentProvider):
    """
    Daraja STK Push scaffold.

    Production wiring: set MPESA_* env vars and replace `_simulate_stk_push`
    with a real Safaricom API call. Callbacks must still verify amount +
    CheckoutRequestID and stay idempotent.
    """

    code = 'mpesa'

    def initiate_payment(self, *, order: Order, phone: str = '') -> Payment:
        # Persist an attempt before network I/O so a timeout cannot trigger a duplicate STK push.
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            _ensure_payable_order(order=order)
            existing = (
                Payment.objects.filter(
                    order=order,
                    provider=self.code,
                    status__in=[PaymentStatusChoice.INITIATED, PaymentStatusChoice.PENDING],
                )
                .order_by('-initiated_at')
                .first()
            )
            if existing:
                return existing

            order.payment_status = PaymentStatus.PROCESSING
            order.save(update_fields=['payment_status', 'updated_at'])
            payment = Payment.objects.create(
                order=order,
                provider=self.code,
                provider_reference=f'MPESA-INIT-{secrets.token_hex(12)}',
                amount=order.grand_total,
                currency=order.currency,
                status=PaymentStatusChoice.INITIATED,
                raw_metadata={
                    'channel': 'stk_push',
                    'phone': phone or '',
                    'initiation_outcome': 'awaiting_provider',
                },
            )

        # Network phase: execute STK push outside the database transaction
        try:
            if getattr(settings, 'MPESA_DARAJA_ENABLED', False):
                stk = self._daraja_client().stk_push(
                    phone=phone,
                    amount=order.grand_total,
                    account_reference=order.public_number,
                    description=f'Order {order.public_number}',
                )
            else:
                stk = self._simulate_stk_push(order=order, phone=phone)
        except Exception as exc:
            Payment.objects.filter(pk=payment.pk).update(
                raw_metadata={
                    **payment.raw_metadata,
                    'initiation_outcome': 'unknown',
                    'initiation_error': type(exc).__name__,
                }
            )
            logger.exception('M-Pesa initiation outcome is unknown for payment %s', payment.pk)
            raise
        checkout_id = stk['CheckoutRequestID']

        # Post-flight: attach Daraja's reference to the durable local attempt.
        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(pk=payment.pk)
                payment.provider_reference = checkout_id
                payment.status = PaymentStatusChoice.PENDING
                payment.raw_metadata = {
                    **payment.raw_metadata,
                    'merchant_request_id': stk.get('MerchantRequestID', ''),
                    'checkout_request_id': checkout_id,
                    'sandbox': not getattr(settings, 'MPESA_LIVE', False),
                    'initiation_outcome': 'accepted',
                }
                payment.save(update_fields=['provider_reference', 'status', 'raw_metadata'])
                return payment
        except Exception:
            logger.critical(
                'Daraja accepted payment %s as checkout %s, but the reference was not persisted',
                payment.pk,
                checkout_id,
                exc_info=True,
            )
            try:
                Payment.objects.filter(pk=payment.pk).update(
                    raw_metadata={
                        **payment.raw_metadata,
                        'checkout_request_id': checkout_id,
                        'initiation_outcome': 'accepted_reference_unpersisted',
                    }
                )
            except Exception:
                logger.critical('Could not preserve checkout ID %s for payment %s', checkout_id, payment.pk, exc_info=True)
            raise

    def _daraja_client(self) -> DarajaClient:
        return DarajaClient(DarajaConfig(
            consumer_key=settings.MPESA_CONSUMER_KEY,
            consumer_secret=settings.MPESA_CONSUMER_SECRET,
            shortcode=settings.MPESA_SHORTCODE,
            passkey=settings.MPESA_PASSKEY,
            callback_url=settings.MPESA_CALLBACK_URL,
            callback_token=settings.MPESA_CALLBACK_SECRET,
            live=settings.MPESA_LIVE,
            timeout=settings.MPESA_HTTP_TIMEOUT,
            transaction_type=settings.MPESA_TRANSACTION_TYPE,
        ))

    def _simulate_stk_push(self, *, order: Order, phone: str) -> dict:
        checkout_id = f'ws_CO_{secrets.token_hex(8)}'
        return {
            'MerchantRequestID': f'mr-{order.public_number}',
            'CheckoutRequestID': checkout_id,
            'ResponseCode': '0',
            'CustomerMessage': 'Success. Request accepted for processing',
            'phone': phone,
        }

    def _verify_callback_signature(self, *, payload: dict) -> bool:
        secret = getattr(settings, 'MPESA_CALLBACK_SECRET', '') or ''
        live = getattr(settings, 'MPESA_LIVE', False)
        if live or secret:
            return bool(payload.get('callback_authenticated'))
        return True  # local scaffold without secret only

    def reconcile_payment(self, *, payment: Payment, checkout_request_id: str = '') -> Payment:
        if payment.provider != self.code:
            raise ValidationError('Payment provider mismatch.')
        if payment.status == PaymentStatusChoice.CONFIRMED:
            return payment
        checkout_id = (
            checkout_request_id.strip()
            or str(payment.raw_metadata.get('checkout_request_id', '')).strip()
            or (payment.provider_reference if not payment.provider_reference.startswith('MPESA-INIT-') else '')
        )
        if not checkout_id:
            raise ValidationError('A Daraja CheckoutRequestID is required to reconcile this payment.')

        result = self._daraja_client().stk_query(checkout_request_id=checkout_id)
        with transaction.atomic():
            payment = Payment.objects.select_for_update().select_related('order').get(pk=payment.pk)
            if payment.status == PaymentStatusChoice.CONFIRMED:
                return payment
            payment.provider_reference = checkout_id
            payment.raw_metadata = {
                **payment.raw_metadata,
                'checkout_request_id': checkout_id,
                'reconciliation': result,
            }
            payment.save(update_fields=['provider_reference', 'raw_metadata'])

        return self.process_callback(
            payload={
                'provider_reference': checkout_id,
                'CheckoutRequestID': checkout_id,
                'ResultCode': result['ResultCode'],
                'amount': str(payment.amount),
                'currency': payment.currency,
                'callback_authenticated': True,
                'reconciled': True,
            }
        )

    @transaction.atomic
    def process_callback(self, *, payload: dict) -> Payment:
        if not self._verify_callback_signature(payload=payload):
            raise ValueError('Invalid M-Pesa callback signature.')
        reference = payload.get('provider_reference') or payload.get('CheckoutRequestID')
        payment = Payment.objects.select_for_update().select_related('order').get(provider_reference=reference)
        if payment.status == PaymentStatusChoice.CONFIRMED:
            return payment
        result_code = str(payload.get('ResultCode', payload.get('result_code', '0')))
        if result_code not in {'0', '00'}:
            return _fail_payment(payment=payment, reason=f'result_code_{result_code}', payload=payload)
        if payload.get('amount') is None:
            return _fail_payment(payment=payment, reason='amount_missing', payload=payload)
        amount = Decimal(str(payload['amount']))
        if amount != payment.amount or payload.get('currency', payment.currency) != payment.currency:
            return _fail_payment(payment=payment, reason='amount_mismatch', payload=payload)
        return _confirm_payment(payment=payment, payload=payload)


def get_provider(code: str | None = None) -> PaymentProvider:
    code = (code or getattr(settings, 'PAYMENT_PROVIDER', 'fake') or 'fake').lower()
    if code == 'fake':
        return FakePaymentProvider()
    if code == 'mpesa':
        return MpesaPaymentProvider()
    raise ValueError(f'Unknown payment provider: {code}')
