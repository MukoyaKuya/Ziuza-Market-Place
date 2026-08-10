"""Payment callback security — fake path must not confirm non-fake payments."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, override_settings

from apps.accounts.models import Address
from apps.marketplace.cart.services import add_to_cart, get_or_create_cart
from apps.marketplace.categories.models import Category
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.orders.models import PaymentStatus
from apps.marketplace.orders.services import create_checkout_order
from apps.marketplace.payments.models import PaymentStatusChoice
from apps.marketplace.payments.providers import get_provider
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def seller(db):
    return User.objects.create_user(email='seller@ziuza.co.ke', password=PASSWORD, display_name='Seller')


@pytest.fixture
def buyer(db):
    return User.objects.create_user(email='buyer@ziuza.co.ke', password=PASSWORD, display_name='Buyer')


@pytest.fixture
def category(db):
    return Category.objects.create(name='Fashion', slug='fashion', is_visible=True)


@pytest.fixture
def shop(seller):
    return create_shop(actor=seller, name='Kiondo Works', county='Nairobi')


@pytest.fixture
def listing(seller, shop, category):
    item = create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title='Sisal Market Basket',
        base_price=Decimal('2500.00'),
        quantity_available=3,
        description='Handwoven sisal',
    )
    publish_listing(actor=seller, listing=item)
    return item


@pytest.fixture
def address(buyer):
    return Address.objects.create(
        user=buyer,
        recipient_name='Buyer Person',
        phone='0712345678',
        address_line_1='12 Ngong Road',
        city_or_town='Nairobi',
        county='Nairobi',
        country='Kenya',
        is_default_shipping=True,
    )


def _checkout_order(client, buyer, listing, address):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    return create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
        shipping_method_code='standard',
        shipping_fee=Decimal('300.00'),
    )


@pytest.fixture
def commerce_order_with_mpesa_pending(client, buyer, listing, address):
    order = _checkout_order(client, buyer, listing, address)
    payment = get_provider('mpesa').initiate_payment(order=order, phone='254712345678')
    return order, payment


@pytest.fixture
def commerce_order_with_fake_pending(client, buyer, listing, address):
    order = _checkout_order(client, buyer, listing, address)
    payment = get_provider('fake').initiate_payment(order=order)
    return order, payment


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_fake_callback_cannot_confirm_mpesa_payment(commerce_order_with_mpesa_pending):
    """POST /payments/callback/fake/ with mpesa CheckoutRequestID must not mark paid."""
    order, payment = commerce_order_with_mpesa_pending
    client = Client()
    resp = client.post(
        '/payments/callback/fake/',
        data={
            'provider_reference': payment.provider_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
        },
    )
    assert resp.status_code in (400, 404)
    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.status != PaymentStatusChoice.CONFIRMED
    assert order.payment_status != PaymentStatus.PAID


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_fake_callback_404_when_not_debug(commerce_order_with_fake_pending):
    order, payment = commerce_order_with_fake_pending
    client = Client()
    resp = client.post(
        '/payments/callback/fake/',
        data={
            'provider_reference': payment.provider_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
        },
    )
    assert resp.status_code == 404


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_fake_callback_rejects_invalid_reference_without_leaking_details(client, buyer, listing, address):
    _checkout_order(client, buyer, listing, address)
    resp = Client().post(
        '/payments/callback/fake/',
        data={
            'provider_reference': 'FAKE-NO-SUCH-ORDER',
            'amount': '2800.00',
            'currency': 'KES',
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body['ok'] is False
    assert body['error'] == 'callback_rejected'
    assert 'DoesNotExist' not in body['error']


@pytest.mark.django_db
def test_fake_payment_reference_includes_unique_nonce(client, buyer, listing, address):
    order = _checkout_order(client, buyer, listing, address)
    payment = get_provider('fake').initiate_payment(order=order)
    prefix = f'FAKE-{order.public_number}-'
    assert payment.provider_reference.startswith(prefix)
    nonce = payment.provider_reference[len(prefix):]
    assert len(nonce) == 8
    assert all(c in '0123456789abcdef' for c in nonce)
