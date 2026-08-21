from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.utils import safe_next_url
from apps.core.htmx import with_toast
from apps.marketplace.favorites.models import (
    CollectionItem,
    Favorite,
    ListingAlert,
    ListingCollection,
    ShopFollow,
)
from apps.marketplace.favorites.services import (
    add_to_collection,
    create_collection,
    remove_from_collection,
    toggle_favorite,
    toggle_listing_alert,
    toggle_shop_follow,
    update_follow_alerts,
)
from apps.marketplace.listings.models import Listing
from apps.marketplace.search.saved import recent_listings_for_user, recommendations_for_user
from apps.marketplace.shops.models import Shop


@require_POST
def toggle_favorite_htmx(request, listing_id):
    if not request.user.is_authenticated:
        next_url = safe_next_url(request, request.headers.get('Referer'), reverse('core:home'))
        login_url = f"{reverse('accounts:login')}?{urlencode({'next': next_url, 'intent': 'favorite'})}"
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Redirect'] = login_url
            return response
        return redirect(login_url)
    try:
        listing = Listing.objects.get(id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404 from exc
    is_favorited, _ = toggle_favorite(actor=request.user, listing=listing)
    response = render(request, 'favorites/partials/button.html', {'listing': listing, 'is_favorited': is_favorited})
    return with_toast(response, message='Saved to Favorites.' if is_favorited else 'Removed from saved items.', type='success')


@login_required
def favorites_list(request):
    favorites = Favorite.objects.filter(user=request.user).select_related(
        'listing', 'listing__shop'
    ).prefetch_related('listing__images')
    collections = ListingCollection.objects.filter(user=request.user).prefetch_related(
        'items__listing__shop', 'items__listing__images'
    )
    follows = ShopFollow.objects.filter(user=request.user).select_related('shop')
    alerts = ListingAlert.objects.filter(user=request.user).select_related('listing', 'listing__shop')
    return render(request, 'favorites/list.html', {
        'favorites': favorites, 'collections': collections, 'follows': follows, 'alerts': alerts,
        'recent_listings': recent_listings_for_user(user=request.user),
        'recommended_listings': recommendations_for_user(user=request.user),
        'page_title': 'Saved & following', 'account_section': 'favorites',
    })


@login_required
@require_POST
def collection_create(request):
    try:
        create_collection(
            actor=request.user, name=request.POST.get('name') or '',
            description=request.POST.get('description') or '', is_public=request.POST.get('is_public') == 'on',
        )
        messages.success(request, 'Collection created.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('favorites:list')


@login_required
@require_POST
def collection_update(request, collection_id):
    try:
        collection = ListingCollection.objects.get(id=collection_id, user=request.user)
    except ListingCollection.DoesNotExist as exc:
        raise Http404 from exc
    collection.description = (request.POST.get('description') or '').strip()[:240]
    collection.is_public = request.POST.get('is_public') == 'on'
    collection.save(update_fields=['description', 'is_public', 'updated_at'])
    messages.success(request, 'Collection privacy updated.')
    return redirect('favorites:list')


@login_required
@require_POST
def collection_add(request, listing_id):
    try:
        listing = Listing.objects.get(id=listing_id)
        collection = ListingCollection.objects.get(id=request.POST.get('collection_id'), user=request.user)
        add_to_collection(actor=request.user, listing=listing, collection=collection)
        messages.success(request, f'Added to {collection.name}.')
    except (Listing.DoesNotExist, ListingCollection.DoesNotExist) as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('favorites:list')


@login_required
@require_POST
def collection_remove(request, item_id):
    try:
        item = CollectionItem.objects.select_related('collection').get(id=item_id, collection__user=request.user)
    except CollectionItem.DoesNotExist as exc:
        raise Http404 from exc
    remove_from_collection(actor=request.user, item=item)
    messages.success(request, 'Removed from collection.')
    return redirect('favorites:list')


def collection_public(request, collection_id):
    try:
        collection = ListingCollection.objects.select_related('user').prefetch_related(
            'items__listing__shop', 'items__listing__images'
        ).get(id=collection_id)
    except ListingCollection.DoesNotExist as exc:
        raise Http404 from exc
    is_owner = request.user.is_authenticated and collection.user_id == request.user.id
    if not collection.is_public and not is_owner:
        raise Http404
    return render(request, 'favorites/collection.html', {
        'collection': collection, 'is_collection_owner': is_owner, 'page_title': collection.name,
    })


@login_required
@require_POST
def shop_follow_toggle(request, shop_id):
    try:
        shop = Shop.objects.get(id=shop_id)
        followed, _ = toggle_shop_follow(actor=request.user, shop=shop)
        messages.success(request, f'{"Following" if followed else "Unfollowed"} {shop.name}.')
    except Shop.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect(safe_next_url(request, request.POST.get('next'), 'favorites:list'))


@login_required
@require_POST
def shop_follow_alerts(request, follow_id):
    try:
        follow = ShopFollow.objects.get(id=follow_id, user=request.user)
    except ShopFollow.DoesNotExist as exc:
        raise Http404 from exc
    update_follow_alerts(actor=request.user, follow=follow, enabled=request.POST.get('enabled') == 'on')
    messages.success(request, 'Shop update preference saved.')
    return redirect('favorites:list')


@login_required
@require_POST
def listing_alert_toggle(request, listing_id):
    try:
        listing = Listing.objects.get(id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404 from exc
    try:
        enabled, _ = toggle_listing_alert(actor=request.user, listing=listing)
        messages.success(request, 'Listing alerts enabled.' if enabled else 'Listing alerts disabled.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect(safe_next_url(request, request.POST.get('next'), 'favorites:list'))
