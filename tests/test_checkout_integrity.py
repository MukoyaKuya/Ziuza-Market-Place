"""Checkout cart lock and one-confirmed-payment-per-order constraint."""

import threading
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import RequestFactory

from apps.accounts.models import Address
from apps.marketplace.cart.models import Cart, CartItem
from apps.marketplace.cart.services import add_to_cart, get_or_create_cart
from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import Inventory
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.orders.models import Order, PaymentStatus
from apps.marketplace.orders.services import create_checkout_order
from apps.marketplace.payments.models import Payment, PaymentStatusChoice
from apps.marketplace.payments.providers import get_provider
from apps.marketplace.shops.models import ShopVerificationStatus
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


# Not transaction=True: TransactionTestCase flushes the whole DB afterwards,
# wiping migration-seeded rows (e.g. ShippingMethod) from the reused file DB and
# breaking later runs. This test is single-connection, so plain TestCase
# semantics are equivalent; real-transaction coverage lives in the concurrent
# test below.
@pytest.mark.django_db
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


@pytest.mark.parametrize('shop_state', ['vacation', 'inactive', 'suspended'])
@pytest.mark.django_db
def test_checkout_rejects_shop_that_became_unavailable(client, buyer, listing, address, shop, shop_state):
    cart = _cart_with_item(client, buyer, listing)
    if shop_state == 'vacation':
        shop.vacation_mode = True
        shop.save(update_fields=['vacation_mode', 'updated_at'])
    elif shop_state == 'inactive':
        shop.is_active = False
        shop.save(update_fields=['is_active', 'updated_at'])
    else:
        shop.verification_status = ShopVerificationStatus.SUSPENDED
        shop.save(update_fields=['verification_status', 'updated_at'])

    with pytest.raises(ValidationError, match='unavailable shop'):
        create_checkout_order(
            actor=buyer,
            cart=cart,
            shipping_address=address,
            shipping_method_code='standard',
            shipping_fee=Decimal('300.00'),
        )

    inventory = Inventory.objects.get(listing=listing, variant__isnull=True)
    assert inventory.quantity_reserved == 0
    assert cart.items.count() == 1
    assert not Order.objects.filter(buyer=buyer).exists()


@pytest.mark.skipif(
    connection.vendor == 'sqlite',
    reason='SQLite does not support row-level locking required for concurrent transaction testing',
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
        except (ValidationError, DatabaseError) as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt_checkout) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert Order.objects.filter(buyer=buyer).count() == 1
    assert len(orders) == 1
    assert len(errors) == 1


@pytest.mark.skipif(
    connection.vendor == 'sqlite',
    reason='SQLite does not support row-level locking required for concurrent transaction testing',
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_payment_callbacks_are_idempotent(client, buyer, listing, address):
    cart = _cart_with_item(client, buyer, listing)
    order = create_checkout_order(
        actor=buyer,
        cart=cart,
        shipping_address=address,
        shipping_method_code='standard',
        shipping_fee=Decimal('300.00'),
    )
    payment = get_provider('fake').initiate_payment(order=order)
    callback = {
        'provider_reference': payment.provider_reference,
        'amount': str(payment.amount),
        'currency': payment.currency,
    }
    results = []
    errors = []
    barrier = threading.Barrier(2)

    def process_callback():
        barrier.wait()
        try:
            connection.ensure_connection()
            results.append(get_provider('fake').process_callback(payload=callback))
        except DatabaseError as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=process_callback) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    payment.refresh_from_db()
    order.refresh_from_db()
    inventory = Inventory.objects.get(listing=listing, variant__isnull=True)
    assert len(results) == 2
    assert not errors
    assert payment.status == PaymentStatusChoice.CONFIRMED
    assert order.payment_status == PaymentStatus.PAID
    assert inventory.quantity_available == 4
    assert inventory.quantity_reserved == 0


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


@pytest.mark.django_db
def test_uniq_cart_per_user(buyer):
    Cart.objects.create(user=buyer)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Cart.objects.create(user=buyer)


@pytest.mark.django_db
def test_uniq_anon_cart_per_session():
    Cart.objects.create(session_key='anon-session-1', user=None)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Cart.objects.create(session_key='anon-session-1', user=None)


@pytest.mark.django_db
def test_get_or_create_cart_reuses_user_cart(client, buyer):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    first = get_or_create_cart(request=request)
    second = get_or_create_cart(request=request)
    assert first.id == second.id
    assert Cart.objects.filter(user=buyer).count() == 1


@pytest.mark.django_db
def test_cartitem_base_variant_uniqueness(buyer, listing):
    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(cart=cart, listing=listing, variant=None, personalization_signature='')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CartItem.objects.create(cart=cart, listing=listing, variant=None, personalization_signature='')


@pytest.mark.django_db
def test_inventory_reserved_lte_available(listing):
    inv = Inventory.objects.get(listing=listing, variant__isnull=True)
    inv.quantity_available = 2
    inv.quantity_reserved = 2
    inv.save()
    inv.quantity_reserved = 3
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            inv.save(update_fields=['quantity_reserved'])
