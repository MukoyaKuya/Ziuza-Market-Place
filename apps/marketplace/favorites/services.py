from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import ensure_authenticated
from apps.marketplace.favorites.models import (
    CollectionItem, Favorite, ListingAlert, ListingCollection, ShopFollow,
)
from apps.marketplace.listings.models import Listing, ListingStatus, ProductType
from apps.marketplace.notifications.services import notify
from apps.marketplace.shops.permissions import user_is_shop_staff


def listing_is_in_stock(listing):
    if listing.product_type == ProductType.DIGITAL:
        return True
    row = listing.inventory_rows.filter(variant__isnull=True).first()
    return bool(row and row.available_to_sell > 0)


def default_collection(*, actor):
    collection, _ = ListingCollection.objects.get_or_create(user=actor, name='Favorites')
    return collection


@transaction.atomic
def toggle_favorite(*, actor, listing: Listing) -> tuple[bool, Favorite | None]:
    ensure_authenticated(actor=actor)
    if listing.status != ListingStatus.ACTIVE:
        Favorite.objects.filter(user=actor, listing=listing).delete()
        CollectionItem.objects.filter(collection__user=actor, listing=listing).delete()
        return False, None
    favorite, created = Favorite.objects.get_or_create(user=actor, listing=listing)
    if not created:
        CollectionItem.objects.filter(collection__user=actor, listing=listing).delete()
        favorite.delete()
        return False, None
    CollectionItem.objects.get_or_create(collection=default_collection(actor=actor), listing=listing)
    return True, favorite


def create_collection(*, actor, name, description='', is_public=False):
    ensure_authenticated(actor=actor)
    name = ' '.join((name or '').split())[:80]
    if len(name) < 2:
        raise ValidationError('Collection name must be at least 2 characters.')
    if ListingCollection.objects.filter(user=actor, name__iexact=name).exists():
        raise ValidationError('You already have a collection with this name.')
    return ListingCollection.objects.create(
        user=actor, name=name, description=(description or '').strip()[:240], is_public=bool(is_public)
    )


@transaction.atomic
def add_to_collection(*, actor, listing, collection):
    ensure_authenticated(actor=actor)
    if collection.user_id != actor.id:
        raise PermissionDenied
    if listing.status != ListingStatus.ACTIVE:
        raise ValidationError('Only active listings can be collected.')
    Favorite.objects.get_or_create(user=actor, listing=listing)
    item, _ = CollectionItem.objects.get_or_create(collection=collection, listing=listing)
    return item


@transaction.atomic
def remove_from_collection(*, actor, item):
    ensure_authenticated(actor=actor)
    if item.collection.user_id != actor.id:
        raise PermissionDenied
    item.delete()


@transaction.atomic
def toggle_shop_follow(*, actor, shop):
    ensure_authenticated(actor=actor)
    if user_is_shop_staff(actor=actor, shop=shop):
        raise ValidationError('You cannot follow a shop you manage.')
    follow, created = ShopFollow.objects.get_or_create(user=actor, shop=shop)
    if not created:
        follow.delete()
        return False, None
    return True, follow


def update_follow_alerts(*, actor, follow, enabled):
    ensure_authenticated(actor=actor)
    if follow.user_id != actor.id:
        raise PermissionDenied
    follow.alerts_enabled = bool(enabled)
    follow.last_checked_at = timezone.now()
    follow.save(update_fields=['alerts_enabled', 'last_checked_at'])
    return follow


@transaction.atomic
def toggle_listing_alert(*, actor, listing):
    ensure_authenticated(actor=actor)
    if user_is_shop_staff(actor=actor, shop=listing.shop):
        raise ValidationError('You cannot watch a listing from a shop you manage.')
    alert = ListingAlert.objects.filter(user=actor, listing=listing).first()
    if alert:
        alert.delete()
        return False, None
    alert = ListingAlert.objects.create(
        user=actor, listing=listing, last_price=listing.base_price,
        was_in_stock=listing_is_in_stock(listing),
    )
    return True, alert


def process_discovery_alerts(*, limit=500):
    now = timezone.now()
    sent = 0
    follow_ids = list(ShopFollow.objects.filter(alerts_enabled=True).values_list('id', flat=True)[:limit])
    for follow_id in follow_ids:
        with transaction.atomic():
            follow = ShopFollow.objects.select_for_update().select_related('user', 'shop').get(id=follow_id)
            new_listings = follow.shop.listings.filter(
                status=ListingStatus.ACTIVE, published_at__gt=follow.last_checked_at
            ).order_by('-published_at')[:5]
            count = len(new_listings)
            if count:
                notify(
                    recipient=follow.user, type='followed_shop_update',
                    title=f'New from {follow.shop.name}',
                    body=f'{count} new listing{"s" if count != 1 else ""} from a shop you follow.',
                    target_url=f'/shop/{follow.shop.slug}/',
                )
                sent += 1
            follow.last_checked_at = now
            follow.save(update_fields=['last_checked_at'])
    alert_ids = list(ListingAlert.objects.values_list('id', flat=True)[:limit])
    for alert_id in alert_ids:
        with transaction.atomic():
            alert = ListingAlert.objects.select_for_update().select_related('user', 'listing').get(id=alert_id)
            listing = alert.listing
            in_stock = listing_is_in_stock(listing)
            changes = []
            if alert.price_change_enabled and listing.base_price != alert.last_price:
                changes.append(f'Price changed from KES {alert.last_price} to KES {listing.base_price}.')
            if alert.back_in_stock_enabled and in_stock and not alert.was_in_stock:
                changes.append('This listing is back in stock.')
            if changes and listing.status == ListingStatus.ACTIVE:
                notify(
                    recipient=alert.user, type='listing_alert', title=f'Update for {listing.title}',
                    body=' '.join(changes), target_url=f'/listing/{listing.slug}/',
                )
                sent += 1
            alert.last_price = listing.base_price
            alert.was_in_stock = in_stock
            alert.last_checked_at = now
            alert.save(update_fields=['last_price', 'was_in_stock', 'last_checked_at'])
    return sent
