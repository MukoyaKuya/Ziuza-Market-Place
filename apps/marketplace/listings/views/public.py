"""Public storefront catalog views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.listings.selectors import (
    get_visible_category,
    listing_reviews,
    public_listing_detail,
    public_listings_for_category,
    related_listings,
    visible_root_categories,
)
from apps.marketplace.shops.models import ReportReason
from apps.marketplace.shops.trust_services import create_report

LISTING_FALLBACK_IMAGES = {
    'art-collectibles': 'images/categories/art.png',
    'craft-supplies': 'images/categories/craft_supplies.png',
    'fashion': 'images/categories/fashion.png',
    'home-living': 'images/categories/home_living.png',
    'jewelry': 'images/categories/jewelry.png',
    'vintage': 'images/categories/vintage.png',
}


def listing_detail(request, slug: str):
    try:
        listing = public_listing_detail(slug=slug)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    cover = listing.images.first()
    fallback_image_path = LISTING_FALLBACK_IMAGES.get(
        listing.category.slug,
        'images/hero_kiondo_basket.png',
    )
    featured_image_url = cover.image.url if cover else static(fallback_image_path)
    inventory_rows = list(listing.inventory_rows.all())
    base_inventory = next((row for row in inventory_rows if row.variant_id is None), None)
    has_available_inventory = listing.product_type == 'digital' or any(
        row.available_to_sell > 0 and (row.variant_id is None or row.variant.is_active)
        for row in inventory_rows
    )
    from apps.marketplace.favorites.selectors import is_listing_favorited

    is_favorited = is_listing_favorited(user=request.user, listing=listing)
    listing_alert_active = False
    if request.user.is_authenticated:
        from apps.marketplace.favorites.models import ListingAlert
        from apps.marketplace.search.saved import record_recent_view

        listing_alert_active = ListingAlert.objects.filter(user=request.user, listing=listing).exists()
        if listing.shop.owner_id != request.user.id:
            record_recent_view(actor=request.user, listing=listing)
    from apps.marketplace.reviews.models import ReviewReportReason

    reviews, review_summary = listing_reviews(listing=listing)
    similar_listings, more_from_shop = related_listings(listing=listing)
    return render(
        request,
        'listings/public/detail.html',
        {
            'listing': listing,
            'cover': cover,
            'featured_image_url': featured_image_url,
            'featured_image_absolute_url': request.build_absolute_uri(featured_image_url),
            'featured_image_is_fallback': cover is None,
            'base_inventory': base_inventory,
            'has_available_inventory': has_available_inventory,
            'page_title': listing.title,
            'is_favorited': is_favorited,
            'listing_alert_active': listing_alert_active,
            'similar_listings': similar_listings,
            'more_from_shop': more_from_shop,
            'reviews': reviews,
            'review_summary': review_summary,
            'review_report_reasons': ReviewReportReason.choices,
            'report_reasons': ReportReason.choices,
            'is_owner': (
                request.user.is_authenticated and listing.shop.owner_id == request.user.id
            ),
            'share_url': request.build_absolute_uri(reverse('listings:detail', kwargs={'slug': listing.slug})),
            'share_text': f'{listing.title} from {listing.shop.name}',
        },
    )


@login_required
@require_POST
def report_listing(request, slug: str):
    try:
        listing = Listing.objects.select_related('shop').get(slug=slug)
        create_report(actor=request.user, listing=listing, reason=request.POST.get('reason') or '', details=request.POST.get('details') or '')
        messages.success(request, 'Report submitted. Ziuza will review it.')
    except Listing.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('listings:detail', slug=slug)


def category_index(request):
    categories = visible_root_categories()
    return render(
        request,
        'categories/index.html',
        {'categories': categories, 'page_title': 'Categories'},
    )


def category_detail(request, slug: str):
    try:
        category = get_visible_category(slug=slug)
    except Category.DoesNotExist as exc:
        raise Http404('Category not found.') from exc

    listings_qs = public_listings_for_category(category=category)
    query = (request.GET.get('q') or '').strip()[:100]
    if query:
        from django.db.models import Q
        listings_qs = listings_qs.filter(
            Q(title__icontains=query) | Q(short_description__icontains=query) | Q(description__icontains=query)
        )
    sort = request.GET.get('sort') or 'newest'
    if sort == 'price_asc':
        listings_qs = listings_qs.order_by('base_price', '-published_at')
    elif sort == 'price_desc':
        listings_qs = listings_qs.order_by('-base_price', '-published_at')

    paginator = Paginator(listings_qs, 24)
    page = paginator.get_page(request.GET.get('page') or 1)

    context = {
        'category': category,
        'listings_page': page,
        'search_query': query,
        'current_sort': sort,
        'page_title': category.seo_title or category.name,
        'meta_description': category.seo_description or category.description,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'categories/partials/listings_grid.html', context)

    return render(request, 'categories/detail.html', context)


def ziuza_picks(request):
    """Ziuza Maridadis — curated items from promoted shops with a rating above 3.0 approved by admin."""
    promoted_listings = (
        Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            shop__is_active=True,
            shop__vacation_mode=False,
            shop__is_promoted=True,
            shop__rating_average__gt=3.0,
        )
        .select_related('shop', 'category')
        .prefetch_related('images')
        .order_by('-shop__rating_average', '-published_at')
    )

    paginator = Paginator(promoted_listings, 24)
    page = paginator.get_page(request.GET.get('page') or 1)

    return render(
        request,
        'listings/ziuza_picks.html',
        {
            'listings_page': page,
            'page_title': 'Ziuza Maridadis | Admin Approved Promoted Artisans',
        },
    )


def zawadi_index(request):
    """Zawadi — Exclusive Gift Section featuring curated gift categories and approved gift sellers."""
    from apps.marketplace.shops.models import ShopGiftApprovalStatus

    gift_parent = Category.objects.filter(slug='gifts').first()
    gift_categories = (
        Category.objects.filter(parent=gift_parent, is_visible=True).order_by('position', 'name')
        if gift_parent
        else Category.objects.filter(slug__icontains='gift', is_visible=True).order_by('position', 'name')
    )

    approved_gift_listings = (
        Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            shop__is_active=True,
            shop__vacation_mode=False,
            shop__gift_approval_status=ShopGiftApprovalStatus.APPROVED,
        )
        .select_related('shop', 'category')
        .prefetch_related('images')
        .order_by('-published_at')
    )

    paginator = Paginator(approved_gift_listings, 24)
    page = paginator.get_page(request.GET.get('page') or 1)

    return render(
        request,
        'categories/zawadi.html',
        {
            'gift_categories': gift_categories,
            'selected_category': None,
            'listings_page': page,
            'page_title': 'Zawadi — Exclusive Gift Section',
        },
    )


def zawadi_category_detail(request, slug: str):
    """Specific gift sub-category page in Zawadi Exclusive Gift Section."""
    try:
        category = Category.objects.get(slug=slug, is_visible=True)
    except Category.DoesNotExist as exc:
        raise Http404('Gift category not found.') from exc

    gift_parent = Category.objects.filter(slug='gifts').first()
    gift_categories = (
        Category.objects.filter(parent=gift_parent, is_visible=True).order_by('position', 'name')
        if gift_parent
        else Category.objects.filter(slug__icontains='gift', is_visible=True).order_by('position', 'name')
    )

    listings_qs = (
        Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            category=category,
            shop__is_active=True,
            shop__vacation_mode=False,
        )
        .select_related('shop', 'category')
        .prefetch_related('images')
        .order_by('-published_at')
    )

    paginator = Paginator(listings_qs, 24)
    page = paginator.get_page(request.GET.get('page') or 1)

    return render(
        request,
        'categories/zawadi.html',
        {
            'gift_categories': gift_categories,
            'selected_category': category,
            'listings_page': page,
            'page_title': f'Zawadi — {category.name}',
        },
    )
