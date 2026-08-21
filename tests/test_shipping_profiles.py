from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.accounts.models import Address
from apps.marketplace.cart.models import Cart, CartItem
from apps.marketplace.cart.services import annotate_cart_totals
from apps.marketplace.categories.models import Category
from apps.marketplace.listings.forms import ListingForm
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.orders.models import Order
from apps.marketplace.orders.services import create_checkout_order
from apps.marketplace.shipping.services import calculate_shipping_quotes, save_shipping_profile
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def shipping_market(db):
    seller = User.objects.create_user(email='shipper@ziuza.co.ke', password=PASSWORD)
    second_seller = User.objects.create_user(email='shipper-two@ziuza.co.ke', password=PASSWORD)
    buyer = User.objects.create_user(email='shipping-buyer@ziuza.co.ke', password=PASSWORD)
    category = Category.objects.create(name='Shipping goods', slug='shipping-goods', is_visible=True)
    shop = create_shop(actor=seller, name='Nairobi Shipper', county='Nairobi')
    second_shop = create_shop(actor=second_seller, name='Mombasa Shipper', county='Mombasa')
    return seller, second_seller, buyer, category, shop, second_shop


def profile_for(*, seller, shop, name='Standard profile', **overrides):
    fields = {
        'name': name,
        'base_fee': Decimal('250.00'),
        'additional_item_fee': Decimal('50.00'),
        'free_shipping_threshold': None,
        'processing_days_min': 1,
        'processing_days_max': 2,
        'delivery_days_min': 2,
        'delivery_days_max': 4,
        'counties': [],
        'offers_delivery': True,
        'allows_local_pickup': False,
        'pickup_fee': Decimal('0.00'),
        'pickup_instructions': '',
        'is_default': False,
        'is_active': True,
    }
    fields.update(overrides)
    return save_shipping_profile(actor=seller, shop=shop, **fields)


def listing_for(*, seller, shop, category, title, profile=None, price='1000.00', quantity=10):
    listing = create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title=title,
        base_price=Decimal(price),
        quantity_available=quantity,
        shipping_profile=profile,
    )
    publish_listing(actor=seller, listing=listing)
    return listing


def line(listing, quantity=1):
    return {
        'item': SimpleNamespace(listing=listing, quantity=quantity),
        'line_total': listing.base_price * quantity,
    }


@pytest.mark.django_db
def test_default_profile_is_assigned_to_new_physical_listing(shipping_market):
    seller, _second, _buyer, category, shop, _second_shop = shipping_market
    profile = profile_for(seller=seller, shop=shop, is_default=True)

    listing = create_listing(
        actor=seller, shop=shop, category=category, title='Default shipped item',
        base_price=Decimal('900.00'), quantity_available=2,
    )

    assert listing.shipping_profile == profile


@pytest.mark.django_db
def test_listing_cannot_use_another_shops_shipping_profile(shipping_market):
    seller, second_seller, _buyer, category, shop, second_shop = shipping_market
    foreign = profile_for(seller=second_seller, shop=second_shop)

    with pytest.raises(ValidationError):
        create_listing(
            actor=seller, shop=shop, category=category, title='Invalid profile item',
            base_price=Decimal('900.00'), shipping_profile=foreign,
        )


@pytest.mark.django_db
def test_quote_aggregates_multi_seller_and_additional_item_fees(shipping_market):
    seller, second_seller, _buyer, category, shop, second_shop = shipping_market
    first_profile = profile_for(seller=seller, shop=shop, base_fee=Decimal(200), additional_item_fee=Decimal(40))
    second_profile = profile_for(seller=second_seller, shop=second_shop, base_fee=Decimal(300), additional_item_fee=Decimal(25))
    first = listing_for(seller=seller, shop=shop, category=category, title='First parcel', profile=first_profile)
    second = listing_for(seller=second_seller, shop=second_shop, category=category, title='Second parcel', profile=second_profile)

    quotes = calculate_shipping_quotes(lines=[line(first, 3), line(second, 1)], county='Nairobi')
    delivery = next(quote for quote in quotes if quote.code == 'seller_delivery')

    assert delivery.fee == Decimal('580.00')
    assert len(delivery.breakdown) == 2
    assert not any(quote.is_pickup for quote in quotes)


@pytest.mark.django_db
def test_free_shipping_threshold_and_single_shop_pickup(shipping_market):
    seller, _second, _buyer, category, shop, _second_shop = shipping_market
    profile = profile_for(
        seller=seller,
        shop=shop,
        free_shipping_threshold=Decimal('1500.00'),
        allows_local_pickup=True,
        pickup_instructions='Collect from Westlands after confirmation.',
    )
    listing = listing_for(
        seller=seller, shop=shop, category=category, title='Free delivery basket',
        profile=profile, price='800.00',
    )

    quotes = calculate_shipping_quotes(lines=[line(listing, 2)], county='Nairobi')

    assert next(quote for quote in quotes if quote.code == 'seller_delivery').fee == Decimal('0.00')
    pickup = next(quote for quote in quotes if quote.code == 'seller_pickup')
    assert pickup.fee == Decimal('0.00')
    assert 'Westlands' in pickup.breakdown[0]['instructions']


@pytest.mark.django_db
def test_unprofiled_listing_keeps_global_shipping_fallback(shipping_market):
    seller, _second, _buyer, category, shop, _second_shop = shipping_market
    listing = listing_for(seller=seller, shop=shop, category=category, title='Legacy delivery item')

    quotes = calculate_shipping_quotes(lines=[line(listing)], county='Nairobi')

    assert any(quote.code == 'standard' for quote in quotes)


@pytest.mark.django_db
def test_checkout_stores_profile_fee_breakdown(shipping_market):
    seller, _second, buyer, category, shop, _second_shop = shipping_market
    profile = profile_for(seller=seller, shop=shop, base_fee=Decimal('275.00'))
    listing = listing_for(seller=seller, shop=shop, category=category, title='Checkout parcel', profile=profile)
    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(cart=cart, listing=listing, quantity=1)
    address = Address.objects.create(
        user=buyer, recipient_name='Buyer', phone='0712345678', address_line_1='1 Market Road',
        city_or_town='Nairobi', county='Nairobi', country='Kenya', is_default_shipping=True,
    )
    totals = annotate_cart_totals(cart)
    quote = calculate_shipping_quotes(lines=totals['lines'], county='Nairobi')[0]

    order = create_checkout_order(
        actor=buyer,
        cart=cart,
        shipping_address=address,
        shipping_method_code=quote.code,
        shipping_fee=quote.fee,
        shipping_breakdown=quote.breakdown,
    )

    assert order.shipping_total == Decimal('275.00')
    assert order.grand_total == Decimal('1275.00')
    assert order.shipping_breakdown[0]['profile'] == profile.name


@pytest.mark.django_db
def test_listing_form_and_profile_edit_are_scoped_to_owned_shop(client, shipping_market):
    seller, second_seller, _buyer, _category, shop, second_shop = shipping_market
    own = profile_for(seller=seller, shop=shop, name='Own shipping')
    foreign = profile_for(seller=second_seller, shop=second_shop, name='Foreign shipping')
    form = ListingForm(shop=shop)

    assert own in form.fields['shipping_profile'].queryset
    assert foreign not in form.fields['shipping_profile'].queryset

    client.force_login(seller)
    response = client.get(reverse('shipping:profiles'), {'edit': foreign.id})
    assert response.status_code == 404


@pytest.mark.django_db
def test_local_pickup_checkout_does_not_require_delivery_address(client, shipping_market):
    seller, _second, buyer, category, shop, _second_shop = shipping_market
    profile = profile_for(
        seller=seller,
        shop=shop,
        offers_delivery=False,
        allows_local_pickup=True,
        pickup_instructions='Bring your confirmation message.',
    )
    listing = listing_for(seller=seller, shop=shop, category=category, title='Pickup parcel', profile=profile)
    CartItem.objects.create(cart=Cart.objects.create(user=buyer), listing=listing, quantity=1)
    client.force_login(buyer)

    response = client.post(reverse('orders:checkout'), {'shipping_method': 'seller_pickup'})

    assert response.status_code == 302
    order = Order.objects.get(buyer=buyer)
    assert order.shipping_address_snapshot == {}
    assert order.shipping_method_code == 'seller_pickup'
    assert order.shipping_breakdown[0]['pickup'] is True
