from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.services import create_listing, publish_listing, update_listing
from apps.marketplace.shops.marketing import save_shop_section
from apps.marketplace.shops.models import ShopSection, ShopSectionItem
from apps.marketplace.shops.services import create_shop


User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def storefront_market(db):
    seller = User.objects.create_user(email='storefront@ziuza.co.ke', password=PASSWORD)
    other_seller = User.objects.create_user(email='other-storefront@ziuza.co.ke', password=PASSWORD)
    category = Category.objects.create(name='Gifts', slug='gifts', is_visible=True)
    shop = create_shop(actor=seller, name='Gifted Kenya', county='Nairobi')
    other_shop = create_shop(actor=other_seller, name='Other Gifts', county='Mombasa')
    first = create_listing(
        actor=seller, shop=shop, category=category, title='Wedding basket',
        base_price=Decimal('2400.00'), quantity_available=5,
    )
    second = create_listing(
        actor=seller, shop=shop, category=category, title='Birthday basket',
        base_price=Decimal('1800.00'), quantity_available=5,
    )
    foreign = create_listing(
        actor=other_seller, shop=other_shop, category=category, title='Foreign basket',
        base_price=Decimal('1500.00'), quantity_available=5,
    )
    for listing, actor in ((first, seller), (second, seller), (foreign, other_seller)):
        publish_listing(actor=actor, listing=listing)
    return seller, other_seller, category, shop, other_shop, first, second, foreign


@pytest.mark.django_db
def test_listing_seo_metadata_and_structured_product_are_rendered(client, storefront_market):
    seller, _other, _category, _shop, _other_shop, listing, _second, _foreign = storefront_market
    update_listing(
        actor=seller,
        listing=listing,
        seo_title='Handwoven Wedding Basket Kenya',
        seo_description='A handcrafted Kenyan wedding basket for meaningful celebrations.',
    )

    response = client.get(reverse('listings:detail', kwargs={'slug': listing.slug}))

    assert response.status_code == 200
    assert b'<meta property="og:title" content="Handwoven Wedding Basket Kenya">' in response.content
    assert b'application/ld+json' in response.content
    assert b'"@type":"Product"' in response.content
    assert b'WhatsApp' in response.content
    assert b'rel="noopener noreferrer"' in response.content


@pytest.mark.django_db
def test_shop_section_rejects_listing_owned_by_another_shop(storefront_market):
    seller, _other, _category, shop, _other_shop, own, _second, foreign = storefront_market

    with pytest.raises(ValidationError):
        save_shop_section(
            actor=seller,
            shop=shop,
            name='Mixed inventory',
            listings=[own, foreign],
        )

    assert not ShopSection.objects.filter(shop=shop).exists()


@pytest.mark.django_db
def test_section_item_model_also_blocks_cross_shop_membership(storefront_market):
    seller, _other, _category, shop, _other_shop, own, _second, foreign = storefront_market
    section = save_shop_section(actor=seller, shop=shop, name='Owned section', listings=[own])

    with pytest.raises(ValidationError):
        ShopSectionItem.objects.create(section=section, listing=foreign)


@pytest.mark.django_db
def test_public_shop_section_filters_owned_active_listings(client, storefront_market):
    seller, _other, _category, shop, _other_shop, first, second, _foreign = storefront_market
    section = save_shop_section(actor=seller, shop=shop, name='Wedding gifts', listings=[first])

    response = client.get(reverse('shops:public_shop', kwargs={'slug': shop.slug}), {'section': section.slug})

    assert response.status_code == 200
    assert first.title.encode() in response.content
    assert second.title.encode() not in response.content
    assert b'Wedding gifts' in response.content


@pytest.mark.django_db
def test_public_shop_renders_rich_seller_storefront(client, storefront_market):
    _seller, _other, _category, shop, _other_shop, first, second, _foreign = storefront_market

    response = client.get(reverse('shops:public_shop', kwargs={'slug': shop.slug}))

    assert response.status_code == 200
    assert b'All items' in response.content
    assert b'About the shop' in response.content
    assert b'Buyer protection' in response.content
    assert b'Shop policy highlights' in response.content
    assert b'Search in shop' in response.content
    assert b'Handmade with care' in response.content
    assert response.context['listing_count'] == 2
    assert response.context['sales_count'] == 0
    assert len(response.context['review_breakdown']) == 5
    assert set(response.context['hero_listings']) == {first, second}


@pytest.mark.django_db
def test_public_shop_catalogue_supports_search_and_sort(client, storefront_market):
    _seller, _other, _category, shop, _other_shop, first, second, _foreign = storefront_market
    url = reverse('shops:public_shop', kwargs={'slug': shop.slug})

    searched = client.get(url, {'q': 'Wedding'})
    assert searched.status_code == 200
    assert first.title.encode() in searched.content
    assert second.title.encode() not in searched.content
    assert searched.context['shop_query'] == 'Wedding'

    sorted_response = client.get(url, {'sort': 'price_asc'})
    assert sorted_response.status_code == 200
    assert list(sorted_response.context['listings']) == [second, first]
    assert sorted_response.context['shop_sort'] == 'price_asc'


@pytest.mark.django_db
def test_hidden_or_unknown_shop_section_is_not_public(client, storefront_market):
    seller, _other, _category, shop, _other_shop, first, _second, _foreign = storefront_market
    section = save_shop_section(
        actor=seller,
        shop=shop,
        name='Private launch',
        listings=[first],
        is_visible=False,
    )

    response = client.get(reverse('shops:public_shop', kwargs={'slug': shop.slug}), {'section': section.slug})

    assert response.status_code == 404


@pytest.mark.django_db
def test_seller_can_update_storefront_search_preview(client, storefront_market):
    seller, _other, _category, shop, _other_shop, _first, _second, _foreign = storefront_market
    client.force_login(seller)

    response = client.post(reverse('shops:storefront'), {
        'action': 'marketing',
        'announcement': 'Christmas orders close on 10 December.',
        'seo_title': 'Kenyan Gift Baskets by Gifted Kenya',
        'seo_description': 'Handwoven gift baskets created in Nairobi, Kenya.',
    })

    assert response.status_code == 302
    shop.refresh_from_db()
    assert shop.announcement.startswith('Christmas orders')
    public = client.get(reverse('shops:public_shop', kwargs={'slug': shop.slug}))
    assert b'Kenyan Gift Baskets by Gifted Kenya' in public.content
    assert b'Christmas orders close' in public.content
    assert b'"@type":"Store"' in public.content


@pytest.mark.django_db
def test_storefront_section_http_form_is_scoped_to_sellers_listings(client, storefront_market):
    seller, _other, _category, shop, _other_shop, own, _second, foreign = storefront_market
    client.force_login(seller)

    response = client.post(reverse('shops:storefront'), {
        'action': 'save_section',
        'name': 'Crafted request',
        'position': '0',
        'is_visible': 'on',
        'listings': [str(own.id), str(foreign.id)],
    })

    assert response.status_code == 200
    assert not ShopSection.objects.filter(shop=shop, name='Crafted request').exists()
