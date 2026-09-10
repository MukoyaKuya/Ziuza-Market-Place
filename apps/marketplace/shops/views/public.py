"""Public storefront views for shops."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.marketplace.listings.selectors import public_listings_for_shop
from apps.marketplace.shops.models import ReportReason, Shop
from apps.marketplace.shops.selectors import (
    get_public_shop_by_slug,
    public_shop_banner_url,
    public_shop_section,
    public_shop_sections,
    shop_active_listing_count,
    shop_follower_count,
    shop_review_context,
    shop_sales_count,
)
from apps.marketplace.shops.trust_services import create_report


@login_required
@require_http_methods(['POST'])
def report_shop(request, slug):
    try:
        shop = Shop.objects.get(slug=slug)
        create_report(actor=request.user, shop=shop, reason=request.POST.get('reason') or '', details=request.POST.get('details') or '')
        messages.success(request, 'Report submitted. Ziuza will review it.')
    except Shop.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('shops:public_shop', slug=slug)


def public_shop(request, slug: str):
    try:
        shop = get_public_shop_by_slug(slug=slug)
    except Shop.DoesNotExist as exc:
        raise Http404('Shop not found.') from exc

    sections = public_shop_sections(shop=shop)
    selected_section = None
    if request.GET.get('section'):
        selected_section = public_shop_section(shop=shop, slug=request.GET['section'])
        if selected_section is None:
            raise Http404('Shop section not found.')
    shop_query = (request.GET.get('q') or '').strip()[:100]
    shop_sort = request.GET.get('sort') or 'newest'
    if shop_sort not in {'newest', 'price_asc', 'price_desc', 'name'}:
        shop_sort = 'newest'
    try:
        shop_limit = min(48, max(8, int(request.GET.get('limit') or 8)))
    except (TypeError, ValueError):
        shop_limit = 8
    listing_results = list(public_listings_for_shop(
        shop=shop, section=selected_section, query=shop_query, sort=shop_sort,
        limit=shop_limit + 1,
    ))
    has_more_listings = len(listing_results) > shop_limit
    listings = listing_results[:shop_limit]
    from apps.marketplace.favorites.selectors import favorited_listing_ids, follows_shop
    from apps.marketplace.shops.permissions import user_is_shop_staff
    is_following = follows_shop(user=request.user, shop=shop)
    is_shop_staff = request.user.is_authenticated and user_is_shop_staff(actor=request.user, shop=shop)
    favorite_listing_ids = favorited_listing_ids(
        user=request.user, listing_ids=[listing.id for listing in listings],
    )
    for listing in listings:
        listing.is_favorited_by_viewer = listing.id in favorite_listing_ids

    review_context = shop_review_context(shop=shop)
    context = {
        'shop': shop,
        'listings': listings,
        'hero_listings': listings[:3],
        'shop_banner_url': public_shop_banner_url(shop=shop),
        'listing_count': shop_active_listing_count(shop=shop),
        'has_more_listings': has_more_listings,
        'next_listing_limit': min(shop_limit + 8, 48),
        'sales_count': shop_sales_count(shop=shop),
        'shop_query': shop_query,
        'shop_sort': shop_sort,
        'page_title': shop.name,
        'is_owner': request.user.is_authenticated and shop.owner_id == request.user.id,
        'is_shop_staff': is_shop_staff,
        'is_following': is_following,
        'follower_count': shop_follower_count(shop=shop),
        'shop_reviews': review_context['recent_reviews'],
        'shop_review_summary': review_context['summary'],
        'review_breakdown': review_context['breakdown'],
        'report_reasons': ReportReason.choices,
        'sections': sections,
        'selected_section': selected_section,
        'shop_share_url': request.build_absolute_uri(reverse('shops:public_shop', kwargs={'slug': shop.slug})),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'shops/partials/shop_items.html', context)

    return render(request, 'shops/public_shop.html', context)
