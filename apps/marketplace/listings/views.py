from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.marketplace.listings.forms import (
    InventoryForm,
    ListingAttributeForm,
    ListingForm,
    ListingImageForm,
    ListingVariantForm,
    ListingOptionForm,
    PersonalizationFieldForm,
    DigitalAssetForm,
)
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.listings.bulk import export_catalog_csv, import_catalog_csv
from apps.marketplace.listings.selectors import (
    get_listing_for_management,
    get_visible_category,
    public_listing_detail,
    public_listings_for_category,
    seller_listings_for_shop,
    visible_root_categories,
)
from apps.marketplace.listings.services import (
    add_listing_image,
    add_listing_variant,
    add_listing_option,
    add_personalization_field,
    add_digital_asset,
    archive_listing,
    create_listing,
    pause_listing,
    publish_listing,
    set_inventory_quantity,
    set_listing_attribute,
    update_listing,
)
from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.models import Shop
from apps.marketplace.shops.selectors import get_shop_for_user
from apps.marketplace.shops.permissions import MANAGE_LISTINGS, ensure_shop_permission
from apps.marketplace.categories.models import Category
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


def _with_shop(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        shop = get_shop_for_user(user=request.user)
        if shop is None:
            messages.info(request, 'Open a shop to manage listings.')
            return redirect('shops:onboarding')
        ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_LISTINGS)
        return view(request, shop, *args, **kwargs)

    wrapped.__name__ = view.__name__
    wrapped.__doc__ = view.__doc__
    return wrapped


def _format_price(amount, currency='KES'):
    return f'{currency} {amount:,.2f}'.replace('.00', '') if currency == 'KES' else f'{amount} {currency}'


@_with_shop
def seller_listing_list(request, shop: Shop):
    listings = seller_listings_for_shop(shop=shop)
    return render(
        request,
        'listings/seller/list.html',
        dashboard_context(actor=request.user,
            shop=shop,
            section='listings',
            listings=listings,
            ListingStatus=ListingStatus,
        ),
    )


@_with_shop
@require_http_methods(['GET', 'POST'])
def seller_listing_create(request, shop: Shop):
    form = ListingForm(request.POST or None, shop=shop)
    if request.method == 'POST' and form.is_valid():
        try:
            listing = create_listing(
                actor=request.user,
                shop=shop,
                category=form.cleaned_data['category'],
                title=form.cleaned_data['title'],
                base_price=form.cleaned_data['base_price'],
                currency=form.cleaned_data['currency'],
                short_description=form.cleaned_data.get('short_description') or '',
                description=form.cleaned_data.get('description') or '',
                sku=form.cleaned_data.get('sku') or '',
                product_type=form.cleaned_data['product_type'],
                quantity_available=form.cleaned_data.get('quantity_available') or 0,
                seo_title=form.cleaned_data.get('seo_title') or '',
                seo_description=form.cleaned_data.get('seo_description') or '',
                shipping_profile=form.cleaned_data.get('shipping_profile'),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Draft listing created.')
            return redirect('listings:seller_detail', listing_id=listing.id)

    return render(
        request,
        'listings/seller/form.html',
        dashboard_context(actor=request.user,
            shop=shop,
            section='listings',
            form=form,
            page_heading='New listing',
            form_action=reverse('listings:seller_create'),
        ),
    )


@_with_shop
def seller_listing_detail(request, shop: Shop, listing_id):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    base_inventory = next((row for row in listing.inventory_rows.all() if row.variant_id is None), None)
    return render(
        request,
        'listings/seller/detail.html',
        dashboard_context(actor=request.user,
            shop=shop,
            section='listings',
            listing=listing,
            base_inventory=base_inventory,
            inventory_form=InventoryForm(
                initial={
                    'quantity_available': base_inventory.quantity_available if base_inventory else 0,
                    'low_stock_threshold': base_inventory.low_stock_threshold if base_inventory else 3,
                }
            ),
            image_form=ListingImageForm(),
            variant_form=ListingVariantForm(listing=listing),
            option_form=ListingOptionForm(),
            personalization_form=PersonalizationFieldForm(),
            digital_asset_form=DigitalAssetForm(),
            attribute_form=ListingAttributeForm(),
        ),
    )


@_with_shop
@require_http_methods(['GET', 'POST'])
def seller_listing_edit(request, shop: Shop, listing_id):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    form = ListingForm(request.POST or None, instance=listing, shop=shop)
    if request.method == 'POST' and form.is_valid():
        try:
            update_listing(
                actor=request.user,
                listing=listing,
                title=form.cleaned_data['title'],
                category=form.cleaned_data['category'],
                short_description=form.cleaned_data.get('short_description') or '',
                description=form.cleaned_data.get('description') or '',
                base_price=form.cleaned_data['base_price'],
                currency=form.cleaned_data['currency'],
                sku=form.cleaned_data.get('sku') or '',
                product_type=form.cleaned_data['product_type'],
                seo_title=form.cleaned_data.get('seo_title') or '',
                seo_description=form.cleaned_data.get('seo_description') or '',
                shipping_profile=form.cleaned_data.get('shipping_profile'),
            )
            qty = form.cleaned_data.get('quantity_available')
            if qty is not None:
                set_inventory_quantity(
                    actor=request.user,
                    listing=listing,
                    quantity_available=qty,
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Listing updated.')
            return redirect('listings:seller_detail', listing_id=listing.id)

    return render(
        request,
        'listings/seller/form.html',
        dashboard_context(actor=request.user,
            shop=shop,
            section='listings',
            form=form,
            listing=listing,
            page_heading='Edit listing',
            form_action=reverse('listings:seller_edit', kwargs={'listing_id': listing.id}),
        ),
    )


def _transition(request, shop, listing_id, service, success_message):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc
    try:
        service(actor=request.user, listing=listing)
    except ValidationError as exc:
        messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
    else:
        messages.success(request, success_message)
    return redirect('listings:seller_detail', listing_id=listing_id)


@_with_shop
@require_POST
def seller_listing_publish(request, shop: Shop, listing_id):
    return _transition(request, shop, listing_id, publish_listing, 'Listing published.')


@_with_shop
@require_POST
def seller_listing_pause(request, shop: Shop, listing_id):
    return _transition(request, shop, listing_id, pause_listing, 'Listing paused.')


@_with_shop
@require_POST
def seller_listing_archive(request, shop: Shop, listing_id):
    return _transition(request, shop, listing_id, archive_listing, 'Listing archived.')


@_with_shop
@require_POST
def seller_listing_inventory(request, shop: Shop, listing_id):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    form = InventoryForm(request.POST)
    if form.is_valid():
        try:
            set_inventory_quantity(
                actor=request.user,
                listing=listing,
                quantity_available=form.cleaned_data['quantity_available'],
                low_stock_threshold=form.cleaned_data['low_stock_threshold'],
            )
            messages.success(request, 'Inventory updated.')
        except ValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Invalid inventory values.')
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
@require_POST
def seller_listing_add_image(request, shop: Shop, listing_id):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    form = ListingImageForm(request.POST, request.FILES)
    if form.is_valid():
        add_listing_image(
            actor=request.user,
            listing=listing,
            image=form.cleaned_data['image'],
            alt_text=form.cleaned_data.get('alt_text') or '',
        )
        messages.success(request, 'Image added.')
    else:
        messages.error(request, 'Could not upload image. Check the file type and try again.')
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
@require_POST
def seller_listing_add_variant(request, shop: Shop, listing_id):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    form = ListingVariantForm(request.POST, listing=listing)
    if form.is_valid():
        try:
            add_listing_variant(
                actor=request.user,
                listing=listing,
                name=form.cleaned_data['name'],
                sku=form.cleaned_data.get('sku') or '',
                price_override=form.cleaned_data.get('price_override'),
                quantity_available=form.cleaned_data['quantity_available'],
                option_values=form.cleaned_data['option_values'],
                cover_image=form.cleaned_data['cover_image'],
            )
            messages.success(request, 'Variant added.')
        except ValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Invalid variant details.')
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
@require_POST
def seller_listing_add_option(request, shop: Shop, listing_id):
    listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    form = ListingOptionForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError(_('Invalid option details.'))
        add_listing_option(actor=request.user, listing=listing, **form.cleaned_data)
        messages.success(request, 'Option group added.')
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
@require_POST
def seller_listing_add_personalization(request, shop: Shop, listing_id):
    listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    form = PersonalizationFieldForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError(_('Invalid personalization field.'))
        add_personalization_field(actor=request.user, listing=listing, **form.cleaned_data)
        messages.success(request, 'Personalization field added.')
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
@require_POST
def seller_listing_add_digital_asset(request, shop: Shop, listing_id):
    listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    form = DigitalAssetForm(request.POST, request.FILES)
    try:
        if not form.is_valid():
            raise ValidationError(_('Invalid digital file.'))
        add_digital_asset(actor=request.user, listing=listing, **form.cleaned_data)
        messages.success(request, 'Digital file added securely.')
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
@require_POST
def seller_listing_add_attribute(request, shop: Shop, listing_id):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    form = ListingAttributeForm(request.POST)
    if form.is_valid():
        set_listing_attribute(
            actor=request.user,
            listing=listing,
            name=form.cleaned_data['name'],
            value=form.cleaned_data['value'],
        )
        messages.success(request, 'Attribute saved.')
    else:
        messages.error(request, 'Invalid attribute.')
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
def seller_inventory_overview(request, shop: Shop):
    listings = seller_listings_for_shop(shop=shop)
    rows = []
    for listing in listings:
        base = listing.base_inventory[0] if getattr(listing, 'base_inventory', None) else None
        rows.append({'listing': listing, 'inventory': base})
    return render(
        request,
        'listings/seller/inventory.html',
        dashboard_context(actor=request.user, shop=shop, section='inventory', rows=rows),
    )


@_with_shop
@require_http_methods(['GET', 'POST'])
def seller_bulk_tools(request, shop: Shop):
    current_operation = None
    if request.method == 'POST':
        current_operation = import_catalog_csv(
            actor=request.user,
            shop=shop,
            uploaded_file=request.FILES.get('catalogue_file'),
            dry_run=request.POST.get('dry_run') == 'on',
        )
        if current_operation.status == 'failed':
            messages.error(request, 'The file was not applied. Fix the errors below and try again.')
        elif current_operation.dry_run:
            messages.success(request, 'Validation passed. No catalogue changes were made.')
        else:
            messages.success(request, 'Catalogue changes applied successfully.')

    operations = shop.bulk_operations.select_related('actor')[:10]
    return render(
        request,
        'listings/seller/bulk_tools.html',
        dashboard_context(actor=request.user,
            shop=shop,
            section='bulk_tools',
            current_operation=current_operation,
            operations=operations,
        ),
    )


@_with_shop
def seller_bulk_export(request, shop: Shop):
    content, _operation = export_catalog_csv(actor=request.user, shop=shop)
    response = HttpResponse(content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ziuza-catalogue.csv"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def listing_detail(request, slug: str):
    try:
        listing = public_listing_detail(slug=slug)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    cover = listing.images.first()
    if cover:
        try:
            if not cover.image.storage.exists(cover.image.name):
                cover = None
        except (OSError, ValueError):
            cover = None
    fallback_image_path = LISTING_FALLBACK_IMAGES.get(
        listing.category.slug,
        'images/hero_kiondo_basket.png',
    )
    featured_image_url = cover.image.url if cover else static(fallback_image_path)
    base_inventory = next((row for row in listing.inventory_rows.all() if row.variant_id is None), None)
    has_available_inventory = listing.product_type == 'digital' or any(
        row.available_to_sell > 0 and (row.variant_id is None or row.variant.is_active)
        for row in listing.inventory_rows.all()
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
    from django.db.models import Avg, Count
    from apps.marketplace.reviews.models import Review, ReviewReportReason

    review_queryset = Review.objects.filter(listing=listing, is_visible=True).select_related('buyer').prefetch_related('media')
    review_summary = review_queryset.aggregate(
        count=Count('id'), overall=Avg('rating'), quality=Avg('quality_rating'),
        shipping=Avg('shipping_rating'), service=Avg('service_rating'),
    )
    reviews = review_queryset[:20]
    related_base = Listing.objects.filter(status=ListingStatus.ACTIVE, shop__is_active=True).exclude(id=listing.id).select_related('shop').prefetch_related('images')
    similar_listings = related_base.filter(category=listing.category).exclude(shop=listing.shop)[:4]
    more_from_shop = related_base.filter(shop=listing.shop)[:4]
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
    from apps.marketplace.listings.models import Listing, ListingStatus

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
    from apps.marketplace.categories.models import Category
    from apps.marketplace.listings.models import Listing, ListingStatus
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
    from apps.marketplace.categories.models import Category
    from apps.marketplace.listings.models import Listing, ListingStatus

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
