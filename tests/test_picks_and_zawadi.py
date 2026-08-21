from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.shops.models import ShopGiftApprovalStatus
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email='artisan@ziuza.co.ke',
        password=PASSWORD,
        display_name='Artisan',
    )


@pytest.fixture
def shop(user):
    return create_shop(
        actor=user,
        name='Craft Artisan Shop',
        county='Nairobi',
    )


@pytest.fixture
def category(db):
    return Category.objects.create(
        name='General Crafts',
        slug='general-crafts',
        is_visible=True,
    )


@pytest.mark.django_db
def test_ziuza_picks_view_renders(client, shop, category):
    shop.is_promoted = True
    shop.rating_average = Decimal('4.5')
    shop.save()

    Listing.objects.create(
        shop=shop,
        category=category,
        title='Promoted Artisanal Bowl',
        base_price=Decimal('2500.00'),
        status=ListingStatus.ACTIVE,
    )

    url = reverse('listings:ziuza_picks')
    response = client.get(url)
    assert response.status_code == 200
    assert b'Ziuza Maridadis' in response.content
    assert b'Promoted Artisanal Bowl' in response.content


@pytest.mark.django_db
def test_zawadi_exclusive_gift_section_renders(client, shop, category):
    shop.gift_approval_status = ShopGiftApprovalStatus.APPROVED
    shop.save()

    kids_gift_cat = Category.objects.create(name='Kids Gifts', slug='kids-gifts', is_visible=True)

    Listing.objects.create(
        shop=shop,
        category=kids_gift_cat,
        title='Handcrafted Kids Toy Set',
        base_price=Decimal('1800.00'),
        status=ListingStatus.ACTIVE,
    )

    url = reverse('listings:zawadi_index')
    response = client.get(url)
    assert response.status_code == 200
    assert b'Zawadi Hub' in response.content

    detail_url = reverse('listings:zawadi_category_detail', kwargs={'slug': 'kids-gifts'})
    detail_resp = client.get(detail_url)
    assert detail_resp.status_code == 200
    assert b'Handcrafted Kids Toy Set' in detail_resp.content


@pytest.mark.django_db
def test_seller_dashboard_gift_request(client, user, shop):
    client.force_login(user)
    url = reverse('shops:dashboard_gifts')

    response = client.get(url)
    assert response.status_code == 200
    assert b'Gift Section (Zawadi)' in response.content

    post_resp = client.post(url, {'action': 'request_approval', 'notes': 'We specialize in custom wood carvings.'})
    assert post_resp.status_code == 302

    shop.refresh_from_db()
    assert shop.gift_approval_status == ShopGiftApprovalStatus.PENDING
    assert shop.gift_request_notes == 'We specialize in custom wood carvings.'


@pytest.mark.django_db
def test_back_to_school_category_and_subcategories(client):
    from django.core.management import call_command
    call_command('seed_categories')

    parent = Category.objects.get(slug='back-to-school')
    assert parent.name == 'Back to School'

    sub_slugs = list(parent.children.values_list('slug', flat=True))
    assert 'school-uniforms' in sub_slugs
    assert 'school-supplies' in sub_slugs
    assert 'university-paraphernalia' in sub_slugs
    assert 'school-books' in sub_slugs
    assert 'boarding-essentials' in sub_slugs
    assert 'school-art-sports' in sub_slugs

    url = reverse('listings:category_detail', kwargs={'slug': 'back-to-school'})
    response = client.get(url)
    assert response.status_code == 200
    assert b'Back to School' in response.content
