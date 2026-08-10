import pytest
from django.template.loader import render_to_string
from django.urls import reverse


@pytest.mark.django_db
def test_design_system_page_renders(client):
    url = reverse('core:design-system')
    response = client.get(url)
    assert response.status_code == 200
    assert b'Ziuza Design System' in response.content
    assert b'Kenya Green' in response.content


@pytest.mark.django_db
def test_design_system_includes_phase1_sections(client):
    response = client.get(reverse('core:design-system'))
    assert response.status_code == 200
    body = response.content
    assert b'Form controls' in body
    assert b'Breadcrumbs' in body
    assert b'Empty, loading' in body
    assert b'Open drawer' in body
    assert b'Open modal' in body
    assert b'Display name' in body
    assert b'Made in Kenya' in body


@pytest.mark.django_db
def test_home_page_renders_hero_and_mockup_sections(client):
    url = reverse('core:home')
    response = client.get(url)
    assert response.status_code == 200
    assert b'Made in' in response.content
    assert b'Ziuza Picks' in response.content
    assert b'Shop by category' in response.content
    assert b'data-marketplace-search' in response.content
    assert b'Search products, shops, and Kenyan makers' in response.content


def test_listing_card_verified_tick_is_controlled_by_verified_flag():
    unverified = render_to_string('components/listing_card/listing_card.html', {
        'title': 'Unverified basket', 'shop_name': 'New maker', 'price': '1200',
        'is_verified': False,
    })
    verified = render_to_string('components/listing_card/listing_card.html', {
        'title': 'Verified basket', 'shop_name': 'Approved maker', 'price': '1200',
        'is_verified': True,
    })

    assert 'data-verification-badge' not in unverified
    assert 'data-verification-badge' in verified
    assert 'aria-label="Verified shop"' in verified


def test_listing_card_uses_category_artwork_when_product_has_no_image():
    card = render_to_string('components/listing_card/listing_card.html', {
        'title': 'Soapstone Elephant',
        'shop_name': 'Coastal Craft Collective',
        'price': '1450',
        'category_slug': 'art-collectibles',
        'image_url': '',
    })

    assert '/static/images/categories/art.png' in card
    assert '/static/images/hero_kiondo_basket.png' not in card
