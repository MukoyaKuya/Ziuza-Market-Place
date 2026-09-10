"""WhatsApp click-to-chat checkout: eligibility, order creation, seller confirmation."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.marketplace.cart.services import add_to_cart, get_or_create_cart
from apps.marketplace.categories.models import Category
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.notifications.models import Notification
from apps.marketplace.orders.models import Order
from apps.marketplace.orders.services import (
    create_checkout_order,
    expire_stale_orders,
    release_order_inventory,
)
from apps.marketplace.payments.models import Payment, PaymentStatusChoice
from apps.marketplace.payments.whatsapp import (
    build_whatsapp_checkout_url,
    confirm_whatsapp_payment,
    normalize_whatsapp_number,
)
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def seller(db):
    return User.objects.create_user(email='wa-seller@ziuza.co.ke', password=PASSWORD, display_name='Seller')


@pytest.fixture
def buyer(db):
    return User.objects.create_user(email='wa-buyer@ziuza.co.ke', password=PASSWORD, display_name='Buyer')


@pytest.fixture
def other_seller(db):
    return User.objects.create_user(email='wa-other@ziuza.co.ke', password=PASSWORD, display_name='Other')


@pytest.fixture
def category(db):
    return Category.objects.create(name='WA Crafts', slug='wa-crafts', is_visible=True)


@pytest.fixture
def shop(seller):
    shop = create_shop(actor=seller, name='WhatsApp Works', county='Nairobi')
    shop.whatsapp_number = '254712345678'
    shop.save(update_fields=['whatsapp_number'])
    return shop


@pytest.fixture
def listing(seller, shop, category):
    item = create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title='Kiondo Basket',
        base_price=Decimal('2500.00'),
        quantity_available=5,
        description='Handwoven sisal basket',
    )
    publish_listing(actor=seller, listing=item)
    return item


@pytest.fixture
def digital_listing(seller, shop, category):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.marketplace.listings.services import add_digital_asset

    item = create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title='Printable Sticker Pack',
        base_price=Decimal('300.00'),
        product_type='digital',
        quantity_available=0,
    )
    add_digital_asset(
        actor=seller,
        listing=item,
        title='Sticker pack PDF',
        file=SimpleUploadedFile('stickers.pdf', b'%PDF-1.4 sticker pack', content_type='application/pdf'),
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


def _cart_with_items(client, user, *listings):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = user
    request.session = client.session
    request.session.save()
    for item in listings:
        add_to_cart(request=request, listing=item, quantity=1)
    return get_or_create_cart(request=request)


# --- number normalization ----------------------------------------------------

@pytest.mark.parametrize('raw,expected', [
    ('0712345678', '254712345678'),
    ('712345678', '254712345678'),
    ('+254 712 345 678', '254712345678'),
    ('254712345678', '254712345678'),
    ('+255712345678', '255712345678'),
])
def test_normalize_whatsapp_number_accepts_common_formats(raw, expected):
    assert normalize_whatsapp_number(raw) == expected


@pytest.mark.parametrize('raw', ['', 'not-a-number', '12345', '+123'])
def test_normalize_whatsapp_number_rejects_garbage(raw):
    with pytest.raises(ValueError):
        normalize_whatsapp_number(raw)


# --- order creation -----------------------------------------------------------

@pytest.mark.django_db
def test_whatsapp_order_gets_long_reservation_window(client, buyer, listing, address):
    cart = _cart_with_items(client, buyer, listing)
    before = timezone.now()

    order = create_checkout_order(
        actor=buyer,
        cart=cart,
        shipping_address=address,
        shipping_method_code='standard',
        shipping_fee=Decimal('300.00'),
        payment_method='whatsapp',
    )

    assert order.payment_method == 'whatsapp'
    assert order.payment_status == 'pending'
    assert order.reservation_expires_at > before
    # ~24h, not the 30-minute online window
    assert timezone.now() + timedelta(hours=23) < order.reservation_expires_at


@pytest.mark.django_db
def test_whatsapp_payment_requires_shop_number(client, buyer, listing, address, shop):
    shop.whatsapp_number = ''
    shop.save(update_fields=['whatsapp_number'])
    cart = _cart_with_items(client, buyer, listing)

    with pytest.raises(ValidationError, match='does not accept WhatsApp'):
        create_checkout_order(
            actor=buyer, cart=cart, shipping_address=address,
            shipping_method_code='standard', shipping_fee=Decimal('300.00'),
            payment_method='whatsapp',
        )


@pytest.mark.django_db
def test_whatsapp_payment_rejected_for_multi_shop_cart(client, buyer, seller, other_seller, listing, category, address):
    other_shop = create_shop(actor=other_seller, name='Other Shop', county='Mombasa')
    other_listing = create_listing(
        actor=other_seller, shop=other_shop, category=category,
        title='Lamu Hat', base_price=Decimal('1200.00'), quantity_available=2,
    )
    publish_listing(actor=other_seller, listing=other_listing)
    cart = _cart_with_items(client, buyer, listing, other_listing)

    with pytest.raises(ValidationError, match='single shop'):
        create_checkout_order(
            actor=buyer, cart=cart, shipping_address=address,
            shipping_method_code='standard', shipping_fee=Decimal('300.00'),
            payment_method='whatsapp',
        )


@pytest.mark.django_db
def test_unknown_payment_method_rejected(client, buyer, listing, address):
    cart = _cart_with_items(client, buyer, listing)
    with pytest.raises(ValidationError, match='payment method'):
        create_checkout_order(
            actor=buyer, cart=cart, shipping_address=address,
            shipping_method_code='standard', shipping_fee=Decimal('300.00'),
            payment_method='carrier-pigeon',
        )


@pytest.mark.django_db
def test_online_orders_keep_short_reservation(client, buyer, listing, address):
    cart = _cart_with_items(client, buyer, listing)

    order = create_checkout_order(
        actor=buyer, cart=cart, shipping_address=address,
        shipping_method_code='standard', shipping_fee=Decimal('300.00'),
    )

    assert order.payment_method == 'online'
    assert order.reservation_expires_at <= timezone.now() + timedelta(hours=1)


# --- wa.me link ---------------------------------------------------------------

@pytest.mark.django_db
def test_whatsapp_url_contains_number_items_and_total(client, buyer, listing, address):
    cart = _cart_with_items(client, buyer, listing)
    order = create_checkout_order(
        actor=buyer, cart=cart, shipping_address=address,
        shipping_method_code='standard', shipping_fee=Decimal('300.00'),
        payment_method='whatsapp',
    )
    from apps.marketplace.shops.models import Shop
    shop = Shop.objects.get(pk=order.seller_orders.first().shop_id)

    url = build_whatsapp_checkout_url(order=order, shop=shop)

    assert url.startswith('https://wa.me/254712345678?')
    assert order.public_number in url
    assert 'KES' in url
    assert str(order.grand_total) in url


# --- seller confirmation --------------------------------------------------------

def _whatsapp_order(client, buyer, listing, address):
    cart = _cart_with_items(client, buyer, listing)
    return create_checkout_order(
        actor=buyer, cart=cart, shipping_address=address,
        shipping_method_code='standard', shipping_fee=Decimal('300.00'),
        payment_method='whatsapp',
    )


@pytest.mark.django_db
def test_confirm_whatsapp_payment_marks_paid_and_notifies_buyer(client, buyer, seller, listing, address):
    order = _whatsapp_order(client, buyer, listing, address)
    seller_order = order.seller_orders.first()

    confirm_whatsapp_payment(actor=seller, seller_order=seller_order)

    order.refresh_from_db()
    assert order.payment_status == 'paid'
    payment = order.payments.get()
    assert payment.provider == 'whatsapp'
    assert payment.status == PaymentStatusChoice.CONFIRMED
    assert payment.amount == order.grand_total
    assert Notification.objects.filter(recipient=buyer, type='payment_confirmed').exists()


@pytest.mark.django_db
def test_confirm_whatsapp_payment_is_idempotent(client, buyer, seller, listing, address):
    order = _whatsapp_order(client, buyer, listing, address)
    seller_order = order.seller_orders.first()

    first = confirm_whatsapp_payment(actor=seller, seller_order=seller_order)
    second = confirm_whatsapp_payment(actor=seller, seller_order=seller_order)

    assert first.pk == second.pk
    assert order.payments.count() == 1
    assert Notification.objects.filter(recipient=buyer, type='payment_confirmed').count() == 1


@pytest.mark.django_db
def test_confirm_whatsapp_payment_rejects_online_orders(client, buyer, seller, listing, address):
    cart = _cart_with_items(client, buyer, listing)
    order = create_checkout_order(
        actor=buyer, cart=cart, shipping_address=address,
        shipping_method_code='standard', shipping_fee=Decimal('300.00'),
    )
    seller_order = order.seller_orders.first()

    with pytest.raises(ValidationError, match='not placed with WhatsApp'):
        confirm_whatsapp_payment(actor=seller, seller_order=seller_order)


@pytest.mark.django_db
def test_confirm_whatsapp_payment_rejects_released_order(client, buyer, seller, listing, address):
    order = _whatsapp_order(client, buyer, listing, address)
    release_order_inventory(order=order)
    seller_order = order.seller_orders.first()

    with pytest.raises(ValidationError, match='expired'):
        confirm_whatsapp_payment(actor=seller, seller_order=seller_order)


@pytest.mark.django_db
def test_whatsapp_order_not_released_before_24h(client, buyer, seller, listing, address):
    order = _whatsapp_order(client, buyer, listing, address)

    expire_stale_orders()

    order.refresh_from_db()
    assert order.payment_status == 'pending'


# --- views ----------------------------------------------------------------------

@pytest.mark.django_db
def test_checkout_view_whatsapp_flow_redirects_to_confirmation_page(client, buyer, shop, digital_listing):
    client.force_login(buyer)
    _cart_with_items(client, buyer, digital_listing)

    response = client.post(
        reverse('orders:checkout'),
        {'payment_method': 'whatsapp', 'coupon_code': ''},
    )

    assert response.status_code == 302
    order = Order.objects.get(buyer=buyer)
    assert response.url == reverse('orders:whatsapp_checkout', kwargs={'public_number': order.public_number})
    assert order.payment_method == 'whatsapp'

    page = client.get(response.url)
    content = page.content.decode()
    assert 'https://wa.me/254712345678' in content
    assert shop.name in content


@pytest.mark.django_db
def test_checkout_view_shows_whatsapp_option_only_when_eligible(client, buyer, shop, digital_listing):
    client.force_login(buyer)
    _cart_with_items(client, buyer, digital_listing)

    page = client.get(reverse('orders:checkout'))
    assert 'Arrange payment on WhatsApp' in page.content.decode()

    shop.whatsapp_number = ''
    shop.save(update_fields=['whatsapp_number'])
    page = client.get(reverse('orders:checkout'))
    assert 'Arrange payment on WhatsApp' not in page.content.decode()


@pytest.mark.django_db
def test_seller_confirm_view_marks_paid(client, buyer, seller, listing, address):
    order = _whatsapp_order(client, buyer, listing, address)
    seller_order = order.seller_orders.first()
    client.force_login(seller)

    response = client.post(reverse('payments:seller_confirm_whatsapp', kwargs={'seller_order_id': seller_order.id}))

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.payment_status == 'paid'


@pytest.mark.django_db
def test_seller_confirm_view_denies_buyer_and_outsiders(client, buyer, other_seller, listing, address):
    order = _whatsapp_order(client, buyer, listing, address)
    seller_order = order.seller_orders.first()

    client.force_login(buyer)
    response = client.post(reverse('payments:seller_confirm_whatsapp', kwargs={'seller_order_id': seller_order.id}))
    assert response.status_code == 404

    client.force_login(other_seller)
    response = client.post(reverse('payments:seller_confirm_whatsapp', kwargs={'seller_order_id': seller_order.id}))
    assert response.status_code == 404

    order.refresh_from_db()
    assert order.payment_status == 'pending'
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_buyer_detail_shows_whatsapp_banner_while_pending(client, buyer, seller, shop, listing, address):
    order = _whatsapp_order(client, buyer, listing, address)
    client.force_login(buyer)

    page = client.get(reverse('orders:buyer_detail', kwargs={'public_number': order.public_number}))
    content = page.content.decode()
    assert 'confirm your payment' in content
    assert 'https://wa.me/254712345678' in content

    confirm_whatsapp_payment(actor=seller, seller_order=order.seller_orders.first())
    page = client.get(reverse('orders:buyer_detail', kwargs={'public_number': order.public_number}))
    assert 'confirm your payment' not in page.content.decode()
