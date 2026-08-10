import pytest
from django.template.loader import render_to_string
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import User

PASSWORD = 'password123'


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_design_system_forbidden_when_debug_false_anonymous(client):
    response = client.get(reverse('core:design-system'))
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_design_system_accessible_when_debug_true_anonymous(client):
    response = client.get(reverse('core:design-system'))
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_design_system_accessible_for_staff_when_debug_false(client):
    staff = User.objects.create_user(
        email='staff@ziuza.co.ke',
        password=PASSWORD,
        display_name='Staff',
        is_staff=True,
    )
    client.force_login(staff)
    response = client.get(reverse('core:design-system'))
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_design_system_page_renders(client):
    url = reverse('core:design-system')
    response = client.get(url)
    assert response.status_code == 200
    assert b'Ziuza Design System' in response.content
    assert b'Kenya Green' in response.content


@pytest.mark.django_db
@override_settings(DEBUG=True)
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


def test_listing_card_omits_favorite_without_listing():
    card = render_to_string('components/listing_card/listing_card.html', {
        'title': 'Mock card',
        'shop_name': 'Demo shop',
        'price': '500',
    })
    assert 'favorites:toggle' not in card
    assert 'Add favorite' not in card


def test_base_layout_includes_skip_link():
    html = render_to_string('layouts/base.html', {'csrf_token': 'test'})
    assert 'href="#main-content"' in html
    assert 'Skip to content' in html


def test_login_password_field_defaults_to_password_type():
    html = render_to_string('accounts/login.html', {'form': type('Form', (), {
        'non_field_errors': [],
        'email': type('Field', (), {'value': '', 'errors': []})(),
        'password': type('Field', (), {'errors': []})(),
    })()})
    assert 'type="password"' in html
    assert 'id="id_password"' in html
