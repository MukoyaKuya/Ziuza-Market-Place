from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.marketplace.categories.models import Category
from apps.marketplace.favorites.models import Favorite
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.notifications.models import Notification
from apps.marketplace.search.models import RecentlyViewedListing, SavedSearch
from apps.marketplace.search.saved import recommendations_for_user, save_search
from apps.marketplace.shops.services import create_shop


User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def retention_market(db):
    seller = User.objects.create_user(email='retention-seller@ziuza.co.ke', password=PASSWORD)
    buyer = User.objects.create_user(email='retention-buyer@ziuza.co.ke', password=PASSWORD)
    other_buyer = User.objects.create_user(email='retention-other@ziuza.co.ke', password=PASSWORD)
    baskets = Category.objects.create(name='Baskets', slug='baskets', is_visible=True)
    jewelry = Category.objects.create(name='Jewelry', slug='jewelry', is_visible=True)
    shop = create_shop(actor=seller, name='Retention Studio', county='Nairobi')
    return seller, buyer, other_buyer, baskets, jewelry, shop


def publish_item(*, seller, shop, category, title):
    listing = create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title=title,
        base_price=Decimal('1200.00'),
        quantity_available=5,
    )
    publish_listing(actor=seller, listing=listing)
    return listing


@pytest.mark.django_db
def test_saving_same_search_updates_instead_of_duplicating(retention_market):
    _seller, buyer, _other, baskets, _jewelry, _shop = retention_market
    first, created = save_search(
        actor=buyer,
        data={'q': 'sisal', 'category': baskets.slug, 'verified': '1'},
        name='First name',
        alerts_enabled=True,
    )
    second, created_again = save_search(
        actor=buyer,
        data={'q': 'sisal', 'category': baskets.slug, 'verified': '1'},
        name='Updated name',
        alerts_enabled=False,
    )

    assert created is True
    assert created_again is False
    assert first.pk == second.pk
    assert SavedSearch.objects.filter(user=buyer).count() == 1
    second.refresh_from_db()
    assert second.name == 'Updated name'
    assert second.alerts_enabled is False


@pytest.mark.django_db
def test_saved_search_management_is_private(client, retention_market):
    _seller, buyer, other_buyer, _baskets, _jewelry, _shop = retention_market
    saved, _ = save_search(actor=buyer, data={'q': 'basket'}, alerts_enabled=True)
    client.force_login(other_buyer)

    response = client.post(reverse('search:delete_saved', kwargs={'saved_id': saved.id}))

    assert response.status_code == 404
    assert SavedSearch.objects.filter(id=saved.id).exists()


@pytest.mark.django_db
def test_product_view_records_only_the_buyers_private_history(client, retention_market):
    seller, buyer, _other, baskets, _jewelry, shop = retention_market
    listing = publish_item(seller=seller, shop=shop, category=baskets, title='Viewed basket')
    client.force_login(buyer)

    client.get(reverse('listings:detail', kwargs={'slug': listing.slug}))
    client.get(reverse('listings:detail', kwargs={'slug': listing.slug}))

    recent = RecentlyViewedListing.objects.get(user=buyer, listing=listing)
    assert recent.view_count == 2
    assert not RecentlyViewedListing.objects.exclude(user=buyer).exists()


@pytest.mark.django_db
def test_seller_view_does_not_pollute_own_recommendations(client, retention_market):
    seller, _buyer, _other, baskets, _jewelry, shop = retention_market
    listing = publish_item(seller=seller, shop=shop, category=baskets, title='Seller preview')
    client.force_login(seller)

    client.get(reverse('listings:detail', kwargs={'slug': listing.slug}))

    assert not RecentlyViewedListing.objects.filter(user=seller).exists()


@pytest.mark.django_db
def test_buyer_can_clear_only_their_recent_history(client, retention_market):
    seller, buyer, other_buyer, baskets, _jewelry, shop = retention_market
    listing = publish_item(seller=seller, shop=shop, category=baskets, title='History basket')
    RecentlyViewedListing.objects.create(user=buyer, listing=listing)
    RecentlyViewedListing.objects.create(user=other_buyer, listing=listing)
    client.force_login(buyer)

    response = client.post(reverse('search:clear_recent'))

    assert response.status_code == 302
    assert not RecentlyViewedListing.objects.filter(user=buyer).exists()
    assert RecentlyViewedListing.objects.filter(user=other_buyer).exists()


@pytest.mark.django_db
def test_alert_command_notifies_once_for_new_matching_listing(retention_market):
    seller, buyer, _other, baskets, _jewelry, shop = retention_market
    saved, _ = save_search(actor=buyer, data={'q': 'sisal', 'category': baskets.slug}, alerts_enabled=True)
    saved.last_checked_at = timezone.now() - timedelta(minutes=1)
    saved.save(update_fields=['last_checked_at', 'updated_at'])
    publish_item(seller=seller, shop=shop, category=baskets, title='New sisal basket')
    publish_item(seller=seller, shop=shop, category=baskets, title='Unrelated wool basket')

    call_command('process_saved_search_alerts')
    call_command('process_saved_search_alerts')

    alerts = Notification.objects.filter(recipient=buyer, type='saved_search_match')
    assert alerts.count() == 1
    assert 'sisal' in alerts.get().target_url


@pytest.mark.django_db
def test_recommendations_follow_favorite_categories_and_exclude_favorites(retention_market):
    seller, buyer, _other, baskets, jewelry, shop = retention_market
    favorite = publish_item(seller=seller, shop=shop, category=baskets, title='Favorite basket')
    recommended = publish_item(seller=seller, shop=shop, category=baskets, title='Recommended basket')
    other_category = publish_item(seller=seller, shop=shop, category=jewelry, title='Silver earrings')
    Favorite.objects.create(user=buyer, listing=favorite)

    results = list(recommendations_for_user(user=buyer))

    assert recommended in results
    assert favorite not in results
    assert other_category not in results
