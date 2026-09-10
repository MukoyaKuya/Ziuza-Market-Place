"""Click-to-chat WhatsApp checkout (wa.me links, no WhatsApp API dependency).

The order is placed on Ziuza like any other; WhatsApp is only the channel where
buyer and seller arrange the actual money transfer (M-Pesa till, cash on
delivery, ...). The seller then confirms receipt from their order dashboard.
"""

from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.marketplace.notifications.services import notify
from apps.marketplace.orders.models import Order, PaymentStatus
from apps.marketplace.orders.services import mark_order_paid
from apps.marketplace.payments.models import Payment, PaymentStatusChoice


def normalize_whatsapp_number(value: str) -> str:
    """Return the number as wa.me expects it (international digits, no '+').

    Accepts Kenyan shorthand (07…, 7…) and full international (+254…, +255…).
    Raises ValueError for anything that is not a plausible WhatsApp number.
    """
    raw = (value or '').strip()
    digits = ''.join(character for character in raw if character.isdigit())
    if not digits:
        raise ValueError('Enter a WhatsApp number, for example 0712345678.')
    has_plus = raw.startswith('+')
    if digits.startswith('254') and len(digits) == 12:
        return digits
    if has_plus and 8 <= len(digits) <= 15:
        return digits
    if not has_plus and digits.startswith('0') and len(digits) == 10:
        return f'254{digits[1:]}'
    if not has_plus and digits.startswith('7') and len(digits) == 9:
        return f'254{digits}'
    raise ValueError(
        'Enter a valid Kenyan WhatsApp number (e.g. 0712345678) or a full '
        'international number (e.g. +255712345678).'
    )


def build_whatsapp_checkout_url(*, order: Order, shop) -> str:
    """Pre-filled chat opener for the buyer to arrange payment with the shop."""
    lines = '\n'.join(
        f'- {item.title_snapshot} × {item.quantity} — KES {item.line_total}'
        for item in order.items.all()
    )
    message = (
        f'Hello {shop.name}! I placed order {order.public_number} on Ziuza '
        f'and would like to arrange payment.\n\n{lines}\n\n'
        f'Total: KES {order.grand_total}\nOrder number: {order.public_number}'
    )
    return f'https://wa.me/{shop.whatsapp_number}?{urlencode({"text": message})}'


@transaction.atomic
def confirm_whatsapp_payment(*, actor, seller_order) -> Payment:
    """Seller confirms they received the money over WhatsApp. Idempotent."""
    order = Order.objects.select_for_update().get(pk=seller_order.order_id)
    if order.payment_method != 'whatsapp':
        raise ValidationError('This order was not placed with WhatsApp payment.')
    if order.payment_status == PaymentStatus.PAID:
        existing = order.payments.filter(status=PaymentStatusChoice.CONFIRMED).first()
        if existing is None:
            raise ValidationError('This order is already paid.')
        return existing
    if order.reservation_released_at:
        raise ValidationError('This order expired before payment was confirmed.')

    payment = Payment.objects.create(
        order=order,
        provider='whatsapp',
        provider_reference=f'whatsapp:{order.public_number}',
        amount=order.grand_total,
        currency=order.currency,
        status=PaymentStatusChoice.CONFIRMED,
        confirmed_at=timezone.now(),
        raw_metadata={
            'confirmed_by': str(actor.pk),
            'shop': str(seller_order.shop_id),
        },
    )
    mark_order_paid(order=order)
    notify(
        recipient=order.buyer,
        type='payment_confirmed',
        title=f'Payment confirmed for {order.public_number}',
        body=f'{seller_order.shop.name} confirmed receiving your payment. Your order is now being processed.',
        target_url=f'/account/orders/{order.public_number}/',
    )
    return payment
