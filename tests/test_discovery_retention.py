from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.marketplace.analytics.selectors import shop_analytics_summary
from apps.marketplace.categories.models import Category
from apps.marketplace.favorites.models import (
    CollectionItem, Favorite, ListingAlert, ListingCollection, ShopFollow,
)
from apps.marketplace.favorites.services import (
    add_to_collection, create_collection, process_discovery_alerts,
    toggle_favorite, toggle_listing_alert, toggle_shop_follow,
)
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.search.saved import recommendations_for_user
from apps.marketplace.shops.models import ShopMembership, ShopTeamRole
from apps.marketplace.shops.services import create_shop


User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def discovery_setup(db):
    seller = User.objects.create_user(email='discover-seller@ziuza.co.ke', password=PASSWORD, display_name='Maker')
    buyer = User.objects.create_user(email='discover-buyer@ziuza.co.ke', password=PASSWORD, display_name='Collector')
    other = User.objects.create_user(email='discover-other@ziuza.co.ke', password=PASSWORD, display_name='Other')
    category = Category.objects.create(name='Discovery Craft', slug='discovery-craft', is_visible=True)
    shop = create_shop(actor=seller, name='Discovery Studio', county='Nairobi')
    listing = create_listing(
        actor=seller, shop=shop, category=category, title='Discovery Basket',
        base_price=Decimal('1200.00'), quantity_available=3,
    )
    publish_listing(actor=seller, listing=listing)
    return seller, buyer, other, category, shop, listing


@pytest.mark.django_db
def test_favorite_uses_default_collection_and_removal_clears_collection_items(discovery_setup):
    _, buyer, _, _, _, listing = discovery_setup
    saved, _ = toggle_favorite(actor=buyer, listing=listing)
    assert saved
    assert Favorite.objects.filter(user=buyer, listing=listing).exists()
    assert CollectionItem.objects.filter(collection__user=buyer, collection__name='Favorites', listing=listing).exists()
    saved, _ = toggle_favorite(actor=buyer, listing=listing)
    assert not saved
    assert not CollectionItem.objects.filter(collection__user=buyer, listing=listing).exists()


@pytest.mark.django_db
def test_collections_enforce_ownership_and_public_privacy(client, discovery_setup):
    _, buyer, other, _, _, listing = discovery_setup
    private = create_collection(actor=buyer, name='Private ideas')
    public = create_collection(actor=buyer, name='Gift ideas', description='Shareable picks', is_public=True)
    add_to_collection(actor=buyer, listing=listing, collection=private)
    add_to_collection(actor=buyer, listing=listing, collection=public)
    with pytest.raises(PermissionDenied):
        add_to_collection(actor=other, listing=listing, collection=private)

    client.force_login(other)
    assert client.get(reverse('favorites:collection_public', kwargs={'collection_id': private.id})).status_code == 404
    public_page = client.get(reverse('favorites:collection_public', kwargs={'collection_id': public.id}))
    assert public_page.status_code == 200
    assert listing.title.encode() in public_page.content


@pytest.mark.django_db
def test_shop_follow_rejects_shop_staff_and_can_be_toggled(discovery_setup):
    seller, buyer, other, _, shop, _ = discovery_setup
    ShopMembership.objects.create(shop=shop, user=other, role=ShopTeamRole.SUPPORT, invited_by=seller)
    with pytest.raises(ValidationError, match='manage'):
        toggle_shop_follow(actor=seller, shop=shop)
    with pytest.raises(ValidationError, match='manage'):
        toggle_shop_follow(actor=other, shop=shop)
    following, follow = toggle_shop_follow(actor=buyer, shop=shop)
    assert following and follow.alerts_enabled
    following, _ = toggle_shop_follow(actor=buyer, shop=shop)
    assert not following


@pytest.mark.django_db
def test_followed_shop_new_listing_alert_runs_once(discovery_setup):
    seller, buyer, _, category, shop, _ = discovery_setup
    toggle_shop_follow(actor=buyer, shop=shop)
    new_listing = create_listing(
        actor=seller, shop=shop, category=category, title='New Followed Find',
        base_price=Decimal('800.00'), quantity_available=2,
    )
    publish_listing(actor=seller, listing=new_listing)
    assert process_discovery_alerts() == 1
    assert buyer.notifications.filter(type='followed_shop_update', target_url=f'/shop/{shop.slug}/').exists()
    assert process_discovery_alerts() == 0


@pytest.mark.django_db
def test_listing_alert_detects_real_price_and_back_in_stock_changes_once(discovery_setup):
    _, buyer, _, _, _, listing = discovery_setup
    inventory = listing.inventory_rows.get(variant__isnull=True)
    inventory.quantity_available = 0
    inventory.save(update_fields=['quantity_available'])
    enabled, alert = toggle_listing_alert(actor=buyer, listing=listing)
    assert enabled and not alert.was_in_stock

    listing.base_price = Decimal('1000.00')
    listing.save(update_fields=['base_price'])
    inventory.quantity_available = 4
    inventory.save(update_fields=['quantity_available'])
    assert process_discovery_alerts() == 1
    notification = buyer.notifications.get(type='listing_alert')
    assert 'Price changed' in notification.body
    assert 'back in stock' in notification.body
    assert process_discovery_alerts() == 0


@pytest.mark.django_db
def test_followed_shop_drives_personalized_recommendations(discovery_setup):
    _, buyer, _, _, shop, listing = discovery_setup
    toggle_shop_follow(actor=buyer, shop=shop)
    recommendations = list(recommendations_for_user(user=buyer))
    assert listing in recommendations


@pytest.mark.django_db
def test_saved_following_page_and_shop_follow_button(client, discovery_setup):
    _, buyer, _, _, shop, listing = discovery_setup
    toggle_favorite(actor=buyer, listing=listing)
    client.force_login(buyer)
    shop_page = client.get(reverse('shops:public_shop', kwargs={'slug': shop.slug}))
    assert b'Follow shop' in shop_page.content
    response = client.post(reverse('favorites:shop_follow_toggle', kwargs={'shop_id': shop.id}), {'next': reverse('favorites:list')})
    assert response.status_code == 302
    saved_page = client.get(reverse('favorites:list'))
    assert saved_page.status_code == 200
    assert b'Discovery Studio' in saved_page.content
    assert b'Discovery Basket' in saved_page.content


@pytest.mark.django_db
def test_guest_hx_favorite_click_redirects_to_login(client, discovery_setup):
    *_, listing = discovery_setup
    response = client.post(
        reverse('favorites:toggle', kwargs={'listing_id': listing.id}),
        HTTP_HX_REQUEST='true',
        HTTP_REFERER=reverse('core:home'),
    )
    assert response.status_code == 204
    assert reverse('accounts:login') in response['HX-Redirect']
    assert 'next=' in response['HX-Redirect']


@pytest.mark.django_db
def test_seller_analytics_include_follow_save_and_returning_viewer_signals(discovery_setup):
    _, buyer, _, _, shop, listing = discovery_setup
    toggle_shop_follow(actor=buyer, shop=shop)
    toggle_favorite(actor=buyer, listing=listing)
    from apps.marketplace.search.saved import record_recent_view
    record_recent_view(actor=buyer, listing=listing)
    record_recent_view(actor=buyer, listing=listing)
    summary = shop_analytics_summary(shop=shop)
    assert summary['follower_count'] == 1
    assert summary['listing_save_count'] == 1
    assert summary['returning_viewers'] == 1
