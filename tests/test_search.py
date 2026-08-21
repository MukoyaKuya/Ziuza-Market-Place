from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.search.services import search_listings, search_with_fallback
from apps.marketplace.shops.models import ShopVerificationStatus
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def search_market(db):
    seller = User.objects.create_user(email='search@ziuza.co.ke', password=PASSWORD)
    category = Category.objects.create(name='Home Decor', slug='home-decor', is_visible=True)
    shop = create_shop(actor=seller, name='Savannah Studio', county='Nairobi')
    return seller, category, shop


def active_listing(*, seller, shop, category, title, description='', price='1000.00', quantity=5):
    listing = create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title=title,
        description=description,
        base_price=Decimal(price),
        quantity_available=quantity,
    )
    publish_listing(actor=seller, listing=listing)
    return listing


@pytest.mark.django_db
def test_exact_title_match_outranks_description_and_featured_signal(search_market):
    seller, category, shop = search_market
    exact = active_listing(seller=seller, shop=shop, category=category, title='Sisal')
    broad = active_listing(
        seller=seller,
        shop=shop,
        category=category,
        title='Coastal wall hanging',
        description='Decor made from sisal',
    )
    broad.is_featured = True
    broad.save(update_fields=['is_featured', 'updated_at'])

    results = list(search_listings(query='sisal'))

    assert results[0] == exact
    assert broad in results


@pytest.mark.django_db
def test_multi_word_search_requires_each_meaningful_term(search_market):
    seller, category, shop = search_market
    matching = active_listing(seller=seller, shop=shop, category=category, title='Woven sisal basket')
    active_listing(seller=seller, shop=shop, category=category, title='Sisal wall art')

    results = list(search_listings(query='sisal basket'))

    assert results == [matching]


@pytest.mark.django_db
def test_typo_fallback_finds_close_marketplace_match(search_market):
    seller, category, shop = search_market
    listing = active_listing(seller=seller, shop=shop, category=category, title='Sisal market basket')

    result = search_with_fallback(query='sissal')

    assert result.used_typo_fallback is True
    assert list(result.listings) == [listing]


@pytest.mark.django_db
def test_search_filters_price_inventory_personalization_and_verification(client, search_market):
    seller, category, shop = search_market
    shop.verification_status = ShopVerificationStatus.VERIFIED
    shop.save(update_fields=['verification_status', 'updated_at'])
    matching = active_listing(
        seller=seller,
        shop=shop,
        category=category,
        title='Personalized woven tray',
        price='2400.00',
    )
    matching.is_personalizable = True
    matching.save(update_fields=['is_personalizable', 'updated_at'])
    active_listing(
        seller=seller,
        shop=shop,
        category=category,
        title='Affordable woven tray',
        price='600.00',
    )

    response = client.get(reverse('search:results'), {
        'q': 'woven tray',
        'min_price': '2000',
        'max_price': '3000',
        'county': 'Nairobi',
        'verified': '1',
        'personalizable': '1',
        'in_stock': '1',
    })

    assert response.status_code == 200
    assert matching.title.encode() in response.content
    assert b'Affordable woven tray' not in response.content


@pytest.mark.django_db
def test_typo_fallback_never_exposes_suspended_shop(search_market):
    seller, category, shop = search_market
    visible = active_listing(seller=seller, shop=shop, category=category, title='Sisal basket')
    blocked_seller = User.objects.create_user(email='blocked-search@ziuza.co.ke', password=PASSWORD)
    blocked_shop = create_shop(actor=blocked_seller, name='Blocked Studio', county='Nakuru')
    blocked = active_listing(
        seller=blocked_seller,
        shop=blocked_shop,
        category=category,
        title='Sisal baskets',
    )
    blocked_shop.verification_status = ShopVerificationStatus.SUSPENDED
    blocked_shop.save(update_fields=['verification_status', 'updated_at'])

    result = search_with_fallback(query='sissal')

    assert visible in list(result.listings)
    assert blocked not in list(result.listings)


@pytest.mark.django_db
def test_autocomplete_includes_products_categories_and_shops(client, search_market):
    seller, category, shop = search_market
    active_listing(seller=seller, shop=shop, category=category, title='Savannah wall basket')

    shop_response = client.get(reverse('search:suggestions'), {'q': 'Savannah'})
    category_response = client.get(reverse('search:suggestions'), {'q': 'Home'})

    assert shop_response.status_code == 200
    assert b'Shop' in shop_response.content
    assert b'Savannah Studio' in shop_response.content
    assert b'Savannah wall basket' in shop_response.content
    assert b'Category' in category_response.content
    assert b'Home Decor' in category_response.content
