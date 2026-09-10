from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import Address
from apps.marketplace.analytics.models import ListingDailyMetric, ShopDailyMetric
from apps.marketplace.analytics.selectors import shop_analytics_summary
from apps.marketplace.analytics.services import (
    ensure_shop_metrics,
    nairobi_today,
    rollup_shop_day,
    rollup_shop_range,
)
from apps.marketplace.cart.services import add_to_cart, get_or_create_cart
from apps.marketplace.categories.models import Category
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.orders.services import create_checkout_order
from apps.marketplace.payments.providers import get_provider
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def seller(db):
    return User.objects.create_user(
        email='analytics-seller@ziuza.co.ke', password=PASSWORD, display_name='Seller'
    )


@pytest.fixture
def buyer(db):
    return User.objects.create_user(
        email='analytics-buyer@ziuza.co.ke', password=PASSWORD, display_name='Buyer'
    )


@pytest.fixture
def category(db):
    return Category.objects.create(name='Craft', slug='craft-analytics', is_visible=True)


@pytest.fixture
def shop(seller):
    return create_shop(actor=seller, name='Analytics Shop', county='Nairobi')


@pytest.fixture
def listing(seller, shop, category):
    item = create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title='Beaded Necklace',
        base_price=Decimal('1500.00'),
        quantity_available=10,
        description='Handmade beads',
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


def _pay_for_listing(*, client, buyer, listing, address, quantity=1):
    rf = RequestFactory()
    req = rf.get('/')
    req.user = buyer
    req.session = client.session
    req.session.save()
    add_to_cart(request=req, listing=listing, quantity=quantity)
    cart = get_or_create_cart(request=req)
    order = create_checkout_order(
        actor=buyer,
        cart=cart,
        shipping_address=address,
        shipping_method_code='standard',
        shipping_fee=Decimal('200.00'),
    )
    provider = get_provider('fake')
    payment = provider.initiate_payment(order=order)
    provider.process_callback(
        payload={
            'provider_reference': payment.provider_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
        }
    )
    order.refresh_from_db()
    return order


@pytest.mark.django_db
def test_rollup_shop_day_is_idempotent(client, buyer, seller, listing, address, shop):
    _pay_for_listing(client=client, buyer=buyer, listing=listing, address=address)
    today = nairobi_today()
    first = rollup_shop_day(shop=shop, day=today)
    second = rollup_shop_day(shop=shop, day=today)
    assert first.id == second.id
    assert ShopDailyMetric.objects.filter(shop=shop, date=today).count() == 1
    assert first.orders == 1
    assert first.units_sold == 1
    assert first.revenue == Decimal('1500.00')
    listing_metric = ListingDailyMetric.objects.get(shop=shop, date=today, listing_uuid=listing.id)
    assert listing_metric.units_sold == 1
    assert listing_metric.title_snapshot == 'Beaded Necklace'


@pytest.mark.django_db
def test_shop_daily_metric_unique_constraint(shop):
    today = nairobi_today()
    ShopDailyMetric.objects.create(shop=shop, date=today, orders=1, revenue=Decimal('10.00'))
    with pytest.raises(IntegrityError):
        ShopDailyMetric.objects.create(shop=shop, date=today, orders=2, revenue=Decimal('20.00'))


@pytest.mark.django_db
def test_dense_daily_series_zero_fills_missing_days(client, buyer, listing, address, shop):
    _pay_for_listing(client=client, buyer=buyer, listing=listing, address=address)
    end = nairobi_today()
    start = end - timedelta(days=6)
    rollup_shop_range(shop=shop, start=start, end=end)
    summary = shop_analytics_summary(shop=shop, days=7)
    assert len(summary['daily']) == 7
    assert summary['daily'][0]['day'] == start
    assert summary['daily'][-1]['day'] == end
    assert summary['order_count'] == 1
    assert summary['units_sold'] == 1
    assert summary['lifetime_order_count'] == 1
    assert sum(row['orders'] for row in summary['daily']) == 1


@pytest.mark.django_db
def test_ensure_shop_metrics_fills_gaps_only(shop):
    end = nairobi_today()
    start = end - timedelta(days=2)
    ShopDailyMetric.objects.create(shop=shop, date=end, orders=0, revenue=Decimal('0.00'))
    filled = ensure_shop_metrics(shop=shop, start=start, end=end)
    assert filled == 2
    assert ShopDailyMetric.objects.filter(shop=shop, date__gte=start, date__lte=end).count() == 3
    filled_again = ensure_shop_metrics(shop=shop, start=start, end=end)
    assert filled_again == 0


@pytest.mark.django_db
def test_analytics_days_query_param(client, buyer, seller, listing, address, shop):
    _pay_for_listing(client=client, buyer=buyer, listing=listing, address=address)
    client.force_login(seller)
    response = client.get(reverse('analytics:seller'), {'days': 7})
    assert response.status_code == 200
    assert response.context['selected_days'] == 7
    assert len(response.context['daily']) == 7
    assert not ShopDailyMetric.objects.exists()
    assert not ListingDailyMetric.objects.exists()

    bad = client.get(reverse('analytics:seller'), {'days': 99})
    assert bad.status_code == 200
    assert bad.context['selected_days'] == 14
    assert len(bad.context['daily']) == 14
