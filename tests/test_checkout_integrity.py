"""Checkout cart lock and one-confirmed-payment-per-order constraint."""

import threading
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import RequestFactory

from apps.accounts.models import Address
from apps.marketplace.cart.services import add_to_cart, get_or_create_cart
from apps.marketplace.categories.models import Category
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.orders.models import Order
from apps.marketplace.orders.services import create_checkout_order
from apps.marketplace.payments.models import Payment, PaymentStatusChoice
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
        quantity_available=5,
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


def _cart_with_item(client, buyer, listing):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    return get_or_create_cart(request=request)


@pytest.mark.django_db(transaction=True)
def test_sequential_double_checkout_second_fails_empty_cart(client, buyer, listing, address):
    cart = _cart_with_item(client, buyer, listing)
    create_checkout_order(
        actor=buyer,
        cart=cart,
        shipping_address=address,
        shipping_method_code='standard',
        shipping_fee=Decimal('300.00'),
    )
    cart.refresh_from_db()
    assert cart.items.count() == 0

    with pytest.raises(ValidationError, match='empty'):
        create_checkout_order(
            actor=buyer,
            cart=cart,
            shipping_address=address,
            shipping_method_code='standard',
            shipping_fee=Decimal('300.00'),
        )


@pytest.mark.django_db(transaction=True)
def test_concurrent_double_checkout_creates_one_order(client, buyer, listing, address):
    cart = _cart_with_item(client, buyer, listing)
    checkout_kwargs = {
        'actor': buyer,
        'cart': cart,
        'shipping_address': address,
        'shipping_method_code': 'standard',
        'shipping_fee': Decimal('300.00'),
    }
    orders = []
    errors = []
    barrier = threading.Barrier(2)

    def attempt_checkout():
        barrier.wait()
        try:
            connection.ensure_connection()
            order = create_checkout_order(**checkout_kwargs)
            orders.append(order)
        except ValidationError as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt_checkout) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(orders) == 1
    assert Order.objects.filter(buyer=buyer).count() == 1
    assert len(errors) + len(orders) == 2


@pytest.mark.django_db
def test_only_one_confirmed_payment_per_order(client, buyer, listing, address):
    cart = _cart_with_item(client, buyer, listing)
    order = create_checkout_order(
        actor=buyer,
        cart=cart,
        shipping_address=address,
        shipping_method_code='standard',
        shipping_fee=Decimal('300.00'),
    )
    Payment.objects.create(
        order=order,
        provider='fake',
        provider_reference='FAKE-FIRST',
        amount=order.grand_total,
        currency=order.currency,
        status=PaymentStatusChoice.CONFIRMED,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Payment.objects.create(
                order=order,
                provider='fake',
                provider_reference='FAKE-SECOND',
                amount=order.grand_total,
                currency=order.currency,
                status=PaymentStatusChoice.CONFIRMED,
            )
