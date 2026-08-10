from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.marketplace.categories.models import Category
from apps.marketplace.content.models import (
    HeroSlide,
    HomepageSection,
    HomepageSectionType,
    VisibilityStatus,
)
from apps.marketplace.content.selectors import (
    featured_shops,
    homepage_discovery,
    live_hero_slides,
    live_homepage_sections,
    rotating_discovery,
)
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.shops.models import ShopVerificationStatus
from apps.marketplace.shops.services import create_shop


@pytest.mark.django_db
def test_home_renders_with_cms_sections(client):
    HomepageSection.objects.create(
        section_type=HomepageSectionType.HERO,
        title='Hero',
        position=0,
        is_visible=True,
    )
    HomepageSection.objects.create(
        section_type=HomepageSectionType.CATEGORIES,
        title='Categories',
        position=10,
        is_visible=True,
    )
    HeroSlide.objects.create(
        title='Made in Kenya Campaign',
        subtitle='Seasonal picks',
        primary_cta_label='Shop Now',
        primary_cta_url='/categories/',
        status=VisibilityStatus.PUBLISHED,
        starts_at=timezone.now(),
    )
    response = client.get(reverse('core:home'))
    assert response.status_code == 200
    assert b'Made in Kenya Campaign' in response.content
    assert b'Shop by category' in response.content


@pytest.mark.django_db
def test_expired_hero_not_live():
    HeroSlide.objects.create(
        title='Expired',
        status=VisibilityStatus.PUBLISHED,
        starts_at=timezone.now() - timezone.timedelta(days=10),
        ends_at=timezone.now() - timezone.timedelta(days=1),
    )
    assert live_hero_slides() == []


@pytest.mark.django_db
def test_unpublished_section_hidden():
    HomepageSection.objects.create(
        section_type=HomepageSectionType.TRUST,
        title='Trust',
        is_visible=False,
    )
    assert live_homepage_sections() == []


@pytest.mark.django_db
def test_rotating_discovery_cycles_through_populated_categories(django_user_model):
    maker = django_user_model.objects.create_user(
        email='discovery-maker@ziuza.co.ke',
        password='SecurePassword123!',
        display_name='Discovery Maker',
    )
    shop = create_shop(actor=maker, name='Discovery Crafts', county='Nairobi')
    home_category = Category.objects.create(name='Home & Living', slug='home-living', position=0, is_visible=True)
    fashion_category = Category.objects.create(name='Fashion', slug='fashion', position=1, is_visible=True)

    home_listing = create_listing(
        actor=maker,
        shop=shop,
        category=home_category,
        title='Carved Serving Bowl',
        base_price=Decimal('2200.00'),
        quantity_available=2,
    )
    fashion_listing = create_listing(
        actor=maker,
        shop=shop,
        category=fashion_category,
        title='Handwoven Kikoy Wrap',
        base_price=Decimal('1650.00'),
        quantity_available=2,
    )
    publish_listing(actor=maker, listing=home_listing)
    publish_listing(actor=maker, listing=fashion_listing)

    first_category, first_listings = rotating_discovery(position=0)
    second_category, second_listings = rotating_discovery(position=1)

    assert first_category == home_category
    assert [listing.id for listing in first_listings] == [home_listing.id]
    assert second_category == fashion_category
    assert [listing.id for listing in second_listings] == [fashion_listing.id]


@pytest.mark.django_db
def test_homepage_discovery_fills_sparse_category_rows(django_user_model):
    maker = django_user_model.objects.create_user(
        email='balanced-discovery@ziuza.co.ke',
        password='SecurePassword123!',
        display_name='Balanced Discovery Maker',
    )
    shop = create_shop(actor=maker, name='Balanced Crafts', county='Nairobi')
    art = Category.objects.create(name='Art & Collectibles', slug='art-collectibles', position=0, is_visible=True)
    jewelry = Category.objects.create(name='Jewelry', slug='jewelry', position=1, is_visible=True)
    elephant = create_listing(
        actor=maker, shop=shop, category=art, title='Soapstone Elephant',
        base_price=Decimal('1450.00'), quantity_available=2,
    )
    necklace = create_listing(
        actor=maker, shop=shop, category=jewelry, title='Maasai Bead Necklace',
        base_price=Decimal('1200.00'), quantity_available=2,
    )
    publish_listing(actor=maker, listing=elephant)
    publish_listing(actor=maker, listing=necklace)

    category, listings, is_mixed = homepage_discovery(position=0, limit=4)

    assert category == art
    assert listings[0] == elephant
    assert necklace in listings
    assert is_mixed is True


@pytest.mark.django_db
def test_seller_spotlight_requires_live_products_and_expands_single_shop(client, django_user_model):
    maker = django_user_model.objects.create_user(
        email='spotlight-maker@ziuza.co.ke', password='SecurePassword123!', display_name='Spotlight Maker',
    )
    empty_maker = django_user_model.objects.create_user(
        email='empty-maker@ziuza.co.ke', password='SecurePassword123!', display_name='Empty Maker',
    )
    shop = create_shop(actor=maker, name='Spotlight Weavers', county='Kisumu', description='Handwoven homeware made beside Lake Victoria.')
    shop.verification_status = ShopVerificationStatus.VERIFIED
    shop.rating_average = Decimal('4.80')
    shop.rating_count = 12
    shop.save(update_fields=['verification_status', 'rating_average', 'rating_count'])
    empty_shop = create_shop(actor=empty_maker, name='Empty Verified Shop', county='Nakuru')
    empty_shop.verification_status = ShopVerificationStatus.VERIFIED
    empty_shop.save(update_fields=['verification_status'])
    category = Category.objects.create(name='Spotlight Decor', slug='spotlight-decor', is_visible=True)
    listing = create_listing(
        actor=maker, shop=shop, category=category, title='Lake Basket',
        base_price=Decimal('1800.00'), quantity_available=2,
    )
    publish_listing(actor=maker, listing=listing)
    HomepageSection.objects.create(
        section_type=HomepageSectionType.FEATURED_SHOPS,
        title='Seller spotlight', position=50, is_visible=True,
    )

    selected = list(featured_shops())
    assert selected == [shop]
    assert selected[0].product_count == 1
    assert len(selected[0].spotlight_listings) == 1

    response = client.get(reverse('core:home'))
    assert response.status_code == 200
    assert b'Meet the makers' in response.content
    assert b'Spotlight Weavers' in response.content
    assert b'Handwoven homeware' in response.content
    assert b'Visit shop' in response.content
    assert empty_shop.name.encode() not in response.content
