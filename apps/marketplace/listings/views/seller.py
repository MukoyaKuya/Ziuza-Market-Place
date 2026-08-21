"""Seller-facing listing management views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.marketplace.listings.bulk import export_catalog_csv, import_catalog_csv
from apps.marketplace.listings.forms import (
    DigitalAssetForm,
    InventoryForm,
    ListingAttributeForm,
    ListingForm,
    ListingImageForm,
    ListingOptionForm,
    ListingVariantForm,
    PersonalizationFieldForm,
)
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.listings.selectors import (
    get_listing_for_management,
    seller_listings_for_shop,
)
from apps.marketplace.listings.services import (
    add_digital_asset,
    add_listing_image,
    add_listing_option,
    add_listing_variant,
    add_personalization_field,
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
from apps.marketplace.shops.permissions import MANAGE_LISTINGS, ensure_shop_permission
from apps.marketplace.shops.selectors import get_shop_for_user


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
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    form = ListingOptionForm(request.POST)
    if form.is_valid():
        try:
            add_listing_option(actor=request.user, listing=listing, **form.cleaned_data)
            messages.success(request, 'Option group added.')
        except ValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Invalid option details.')
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
@require_POST
def seller_listing_add_personalization(request, shop: Shop, listing_id):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    form = PersonalizationFieldForm(request.POST)
    if form.is_valid():
        try:
            add_personalization_field(actor=request.user, listing=listing, **form.cleaned_data)
            messages.success(request, 'Personalization field added.')
        except ValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Invalid personalization field.')
    return redirect('listings:seller_detail', listing_id=listing.id)


@_with_shop
@require_POST
def seller_listing_add_digital_asset(request, shop: Shop, listing_id):
    try:
        listing = get_listing_for_management(shop=shop, listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise Http404('Listing not found.') from exc

    form = DigitalAssetForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            add_digital_asset(actor=request.user, listing=listing, **form.cleaned_data)
            messages.success(request, 'Digital file added securely.')
        except ValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Invalid digital file.')
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
