from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.marketplace.listings.selectors import visible_root_categories
from apps.marketplace.search.models import RecentlyViewedListing, SavedSearch
from apps.marketplace.search.saved import (
    recent_listings_for_user,
    recommendations_for_user,
    save_search,
    saved_search_url,
)
from apps.marketplace.search.services import PRODUCT_TYPES, SORT_OPTIONS, search_with_fallback, suggest_discovery
from apps.marketplace.shops.models import Shop, ShopVerificationStatus


def _price(value):
    if not value:
        return None
    try:
        parsed = Decimal(value)
        return parsed if parsed >= 0 else None
    except (InvalidOperation, ValueError):
        return None


@require_GET
def search_results(request):
    query = request.GET.get('q', '')[:100]
    category_slug = request.GET.get('category') or None
    sort = request.GET.get('sort') or 'relevance'
    sort = sort if sort in SORT_OPTIONS else 'relevance'
    min_price = _price(request.GET.get('min_price'))
    max_price = _price(request.GET.get('max_price'))
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price
    product_type = request.GET.get('product_type') or None
    product_type = product_type if product_type in PRODUCT_TYPES else None
    county = (request.GET.get('county') or '').strip()[:100]
    verified_only = request.GET.get('verified') == '1'
    personalizable_only = request.GET.get('personalizable') == '1'
    in_stock_only = request.GET.get('in_stock') == '1'

    result = search_with_fallback(
        query=query,
        category_slug=category_slug,
        min_price=min_price,
        max_price=max_price,
        shop_slug=request.GET.get('shop') or None,
        sort=sort,
        product_type=product_type,
        county=county or None,
        verified_only=verified_only,
        personalizable_only=personalizable_only,
        in_stock_only=in_stock_only,
    )
    page = Paginator(result.listings, 24).get_page(request.GET.get('page') or 1)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    template = (
        'search/partials/grid.html'
        if request.headers.get('HX-Request') == 'true'
        else 'search/results.html'
    )
    return render(
        request,
        template,
        {
            'listings_page': page,
            'query': query,
            'sort': sort,
            'category_slug': category_slug or '',
            'categories': visible_root_categories(),
            'min_price': request.GET.get('min_price', ''),
            'max_price': request.GET.get('max_price', ''),
            'product_type': product_type or '',
            'county': county,
            'counties': Shop.objects.filter(is_active=True, vacation_mode=False)
                .exclude(verification_status=ShopVerificationStatus.SUSPENDED)
                .exclude(county='').values_list('county', flat=True).distinct().order_by('county'),
            'verified_only': verified_only,
            'personalizable_only': personalizable_only,
            'in_stock_only': in_stock_only,
            'used_typo_fallback': result.used_typo_fallback,
            'filter_query': query_params.urlencode(),
            'page_title': f'Search{" · " + query if query else ""}',
        },
    )


@require_GET
def search_suggestions(request):
    query = request.GET.get('q', '')[:100]
    suggestions = suggest_discovery(query=query)
    return render(
        request,
        'search/partials/suggestions.html',
        {
            'suggestions': suggestions.listings,
            'category_suggestions': suggestions.categories,
            'shop_suggestions': suggestions.shops,
            'query': query,
        },
    )


@login_required
@require_POST
def save_current_search(request):
    _saved, created = save_search(
        actor=request.user,
        data=request.POST,
        name=request.POST.get('name') or '',
        alerts_enabled=request.POST.get('alerts_enabled') == 'on',
    )
    messages.success(request, 'Search saved.' if created else 'Saved search updated.')
    return redirect('search:saved')


@login_required
@require_GET
def saved_searches(request):
    saved = list(SavedSearch.objects.filter(user=request.user))
    for item in saved:
        item.result_url = saved_search_url(item)
    return render(request, 'search/saved.html', {
        'saved_searches': saved,
        'recent_listings': recent_listings_for_user(user=request.user),
        'recommendations': recommendations_for_user(user=request.user),
        'account_section': 'saved_searches',
        'page_title': 'Saved searches',
    })


@login_required
@require_POST
def toggle_saved_search_alerts(request, saved_id):
    saved = get_object_or_404(SavedSearch, id=saved_id, user=request.user)
    saved.alerts_enabled = not saved.alerts_enabled
    update_fields = ['alerts_enabled', 'updated_at']
    if saved.alerts_enabled:
        saved.last_checked_at = timezone.now()
        update_fields.append('last_checked_at')
    saved.save(update_fields=update_fields)
    messages.success(request, 'Search alerts enabled.' if saved.alerts_enabled else 'Search alerts paused.')
    return redirect('search:saved')


@login_required
@require_POST
def delete_saved_search(request, saved_id):
    saved = get_object_or_404(SavedSearch, id=saved_id, user=request.user)
    saved.delete()
    messages.success(request, 'Saved search removed.')
    return redirect('search:saved')


@login_required
@require_POST
def clear_recently_viewed(request):
    RecentlyViewedListing.objects.filter(user=request.user).delete()
    messages.success(request, 'Recently viewed history cleared.')
    return redirect('search:saved')
