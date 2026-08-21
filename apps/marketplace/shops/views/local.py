"""Ziuza Local discovery and shop local-program settings views."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.locations import get_counties, get_sub_counties, get_wards
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.forms import ShopLocalSettingsForm
from apps.marketplace.shops.models import Shop, ShopVerificationStatus
from apps.marketplace.shops.permissions import ensure_shop_owner
from apps.marketplace.shops.services import update_shop_settings
from apps.marketplace.shops.views.dashboard import _with_shop


def local_index(request):
    """Ziuza Local discovery page: filter shops and listings by county, sub-county, and ward."""
    county = (request.GET.get('county') or '').strip()
    sub_county = (request.GET.get('sub_county') or '').strip()
    ward = (request.GET.get('ward') or '').strip()
    pickup_only = request.GET.get('pickup') == '1'
    delivery_only = request.GET.get('delivery') == '1'
    query = (request.GET.get('q') or '').strip()[:100]

    all_counties = get_counties()
    available_sub_counties = get_sub_counties(county) if county else []
    available_wards = get_wards(sub_county) if sub_county else []

    # Filter local shops
    shops_qs = (
        Shop.objects.filter(is_active=True, is_local_seller=True)
        .exclude(verification_status=ShopVerificationStatus.SUSPENDED)
        .order_by('-rating_average', '-created_at')
    )
    if county:
        shops_qs = shops_qs.filter(county__iexact=county)
    if sub_county:
        shops_qs = shops_qs.filter(sub_county__iexact=sub_county)
    if ward:
        shops_qs = shops_qs.filter(ward__iexact=ward)
    if pickup_only:
        shops_qs = shops_qs.filter(local_pickup_available=True)
    if query:
        shops_qs = shops_qs.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(location_text__icontains=query)
            | Q(village__icontains=query)
        )

    # Filter local listings
    listings_qs = (
        Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            shop__is_active=True,
            shop__is_local_seller=True,
        )
        .exclude(shop__verification_status=ShopVerificationStatus.SUSPENDED)
        .select_related('shop', 'category')
        .prefetch_related('images')
        .order_by('-published_at')
    )
    if county:
        listings_qs = listings_qs.filter(shop__county__iexact=county)
    if sub_county:
        listings_qs = listings_qs.filter(shop__sub_county__iexact=sub_county)
    if ward:
        listings_qs = listings_qs.filter(shop__ward__iexact=ward)
    if pickup_only:
        listings_qs = listings_qs.filter(shop__local_pickup_available=True)
    if query:
        listings_qs = listings_qs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(shop__name__icontains=query)
        )

    # Paginate shops
    shops_page = Paginator(shops_qs, 12).get_page(request.GET.get('page') or 1)
    listings_sample = listings_qs[:8]

    context = {
        'county': county,
        'sub_county': sub_county,
        'ward': ward,
        'pickup_only': pickup_only,
        'delivery_only': delivery_only,
        'query': query,
        'counties': all_counties,
        'sub_counties': available_sub_counties,
        'wards': available_wards,
        'shops_page': shops_page,
        'total_shops_count': shops_qs.count(),
        'listings_sample': listings_sample,
        'page_title': f'Ziuza Local · {ward or sub_county or county or "Kenya"} Local Makers & Artisans',
    }

    if request.headers.get('HX-Request') == 'true':
        return render(request, 'pages/partials/local_shops_grid.html', context)
    return render(request, 'pages/local.html', context)


def location_sub_counties_options(request):
    """Return HTML <option> tags for sub-counties of given county."""
    county = (request.GET.get('county') or '').strip()
    selected = (request.GET.get('selected') or '').strip()
    sub_counties = get_sub_counties(county) if county else []
    options = ['<option value="">All Sub-Counties</option>']
    for sc in sub_counties:
        is_sel = ' selected' if sc.lower() == selected.lower() else ''
        options.append(f'<option value="{sc}"{is_sel}>{sc}</option>')
    return HttpResponse(''.join(options), content_type='text/html')


def location_wards_options(request):
    """Return HTML <option> tags for wards of given sub-county."""
    sub_county = (request.GET.get('sub_county') or '').strip()
    selected = (request.GET.get('selected') or '').strip()
    wards = get_wards(sub_county) if sub_county else []
    options = ['<option value="">All Wards / Areas</option>']
    for w in wards:
        is_sel = ' selected' if w.lower() == selected.lower() else ''
        options.append(f'<option value="{w}"{is_sel}>{w}</option>')
    return HttpResponse(''.join(options), content_type='text/html')


@_with_shop
@require_http_methods(['GET', 'POST'])
def dashboard_local_settings(request, shop):
    """Manage Ziuza Local program settings, county, sub-county, ward, and pickup details."""
    ensure_shop_owner(actor=request.user, shop=shop)
    form = ShopLocalSettingsForm(request.POST or None, instance=shop)
    if request.method == 'POST' and form.is_valid():
        update_shop_settings(actor=request.user, shop=shop, **form.cleaned_data)
        messages.success(request, 'Ziuza Local settings updated successfully.')
        return redirect('shops:dashboard_local')

    return render(
        request,
        'shops/dashboard/local_settings.html',
        dashboard_context(
            actor=request.user,
            shop=shop,
            section='local',
            form=form,
            sub_counties=get_sub_counties(shop.county),
            wards=get_wards(shop.sub_county) if shop.sub_county else [],
        ),
    )
