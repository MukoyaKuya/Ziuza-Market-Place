from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.permissions import ensure_authenticated
from apps.marketplace.listings.models import (
    Inventory,
    Listing,
    ListingAttribute,
    ListingImage,
    ListingStatus,
    ListingVariant,
    ListingOption,
    ListingOptionValue,
    PersonalizationField,
    PersonalizationFieldType,
    DigitalAsset,
    ProductType,
)
from apps.marketplace.shops.models import Shop
from apps.marketplace.shops.permissions import MANAGE_LISTINGS, ensure_shop_permission

MAX_DIGITAL_ASSET_SIZE = 50 * 1024 * 1024
ALLOWED_DIGITAL_ASSET_TYPES = {
    'application/pdf',
    'application/zip',
    'image/jpeg',
    'image/png',
    'image/webp',
}


def _digital_asset_signature_matches(uploaded_file, content_type):
    header = uploaded_file.read(12)
    uploaded_file.seek(0)
    return {
        'image/jpeg': header.startswith(b'\xff\xd8\xff'),
        'image/png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'image/webp': header.startswith(b'RIFF') and header[8:12] == b'WEBP',
        'application/pdf': header.startswith(b'%PDF-'),
        'application/zip': header.startswith(b'PK\x03\x04') or header.startswith(b'PK\x05\x06') or header.startswith(b'PK\x07\x08'),
    }.get(content_type, False)


def _audit_listing(*, actor, listing, action, description):
    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(
        shop=listing.shop, actor=actor, action=action, target=listing, description=description,
    )


def ensure_actor_can_manage_listing(*, actor, listing: Listing) -> Listing:
    ensure_authenticated(actor=actor)
    ensure_shop_permission(actor=actor, shop=listing.shop, permission=MANAGE_LISTINGS)
    return listing


def _ensure_base_inventory(listing: Listing) -> Inventory:
    inventory, _ = Inventory.objects.get_or_create(
        listing=listing,
        variant=None,
        defaults={'quantity_available': 0, 'quantity_reserved': 0},
    )
    return inventory


@transaction.atomic
def create_listing(
    *,
    actor,
    shop: Shop,
    category,
    title: str,
    base_price,
    currency: str = 'KES',
    short_description: str = '',
    description: str = '',
    sku: str = '',
    quantity_available: int = 0,
    product_type: str = ProductType.PHYSICAL,
    seo_title: str = '',
    seo_description: str = '',
    shipping_profile=None,
) -> Listing:
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_LISTINGS)
    title = (title or '').strip()
    if not title:
        raise ValidationError({'title': _('Title is required.')})
    if shipping_profile is not None and shipping_profile.shop_id != shop.id:
        raise ValidationError({'shipping_profile': _('Shipping profile must belong to this shop.')})
    if shipping_profile is None and product_type != ProductType.DIGITAL:
        shipping_profile = shop.shipping_profiles.filter(is_default=True, is_active=True).first()

    listing = Listing(
        shop=shop,
        category=category,
        title=title,
        short_description=(short_description or '').strip(),
        description=(description or '').strip(),
        base_price=base_price,
        currency=(currency or 'KES').upper()[:3],
        sku=(sku or '').strip(),
        status=ListingStatus.DRAFT,
        product_type=product_type,
        seo_title=(seo_title or '').strip(),
        seo_description=(seo_description or '').strip(),
        shipping_profile=shipping_profile,
    )
    listing.save()
    inventory = _ensure_base_inventory(listing)
    inventory.quantity_available = max(0, int(quantity_available))
    inventory.save(update_fields=['quantity_available', 'updated_at'])
    _audit_listing(actor=actor, listing=listing, action='listing.created', description=f'Created listing “{listing.title}”.')
    return listing


@transaction.atomic
def update_listing(*, actor, listing: Listing, **fields) -> Listing:
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    if listing.status == ListingStatus.ARCHIVED:
        raise ValidationError(_('Archived listings cannot be edited.'))

    allowed = {
        'title',
        'category',
        'short_description',
        'description',
        'base_price',
        'currency',
        'sku',
        'product_type',
        'is_featured',
        'seo_title',
        'seo_description',
        'shipping_profile',
    }
    shipping_profile = fields.get('shipping_profile')
    if shipping_profile is not None and shipping_profile.shop_id != listing.shop_id:
        raise ValidationError({'shipping_profile': _('Shipping profile must belong to this shop.')})
    for key, value in fields.items():
        if key in allowed:
            setattr(listing, key, value)
    listing.save()
    _audit_listing(actor=actor, listing=listing, action='listing.updated', description=f'Updated listing “{listing.title}”.')
    return listing


def ensure_listing_is_publishable(listing: Listing) -> None:
    if listing.status in {ListingStatus.ARCHIVED, ListingStatus.REJECTED}:
        raise ValidationError(_('This listing cannot be published from its current state.'))
    if not listing.title.strip():
        raise ValidationError({'title': _('Title is required to publish.')})
    if listing.base_price is None:
        raise ValidationError({'base_price': _('Price is required to publish.')})
    if listing.product_type == ProductType.DIGITAL:
        if not listing.digital_assets.filter(is_active=True).exists():
            raise ValidationError(_('At least one digital file is required to publish.'))
        return
    inventory = listing.inventory_rows.filter(variant__isnull=True).first()
    if inventory is None and not listing.inventory_rows.filter(variant__isnull=False).exists():
        raise ValidationError(_('Inventory must be configured before publishing.'))


@transaction.atomic
def publish_listing(*, actor, listing: Listing) -> Listing:
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    ensure_listing_is_publishable(listing)
    if listing.product_type == ProductType.DIGITAL:
        listing.status = ListingStatus.ACTIVE
        listing.published_at = timezone.now()
        listing.save(update_fields=['status', 'published_at', 'updated_at'])
        _audit_listing(actor=actor, listing=listing, action='listing.published', description=f'Published listing “{listing.title}”.')
        return listing
    inventory_rows = list(listing.inventory_rows.select_for_update().select_related('variant'))
    has_stock = any(row.available_to_sell > 0 and (row.variant_id is None or row.variant.is_active) for row in inventory_rows)
    listing.status = (
        ListingStatus.ACTIVE if has_stock else ListingStatus.SOLD_OUT
    )
    listing.published_at = timezone.now()
    listing.save(update_fields=['status', 'published_at', 'updated_at'])
    _audit_listing(actor=actor, listing=listing, action='listing.published', description=f'Published listing “{listing.title}”.')
    return listing


@transaction.atomic
def pause_listing(*, actor, listing: Listing) -> Listing:
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    if listing.status not in {ListingStatus.ACTIVE, ListingStatus.SOLD_OUT}:
        raise ValidationError(_('Only active or sold-out listings can be paused.'))
    listing.status = ListingStatus.PAUSED
    listing.save(update_fields=['status', 'updated_at'])
    _audit_listing(actor=actor, listing=listing, action='listing.paused', description=f'Paused listing “{listing.title}”.')
    return listing


@transaction.atomic
def archive_listing(*, actor, listing: Listing) -> Listing:
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    listing.status = ListingStatus.ARCHIVED
    listing.save(update_fields=['status', 'updated_at'])
    _audit_listing(actor=actor, listing=listing, action='listing.archived', description=f'Archived listing “{listing.title}”.')
    return listing


@transaction.atomic
def set_inventory_quantity(
    *,
    actor,
    listing: Listing,
    quantity_available: int,
    variant: ListingVariant | None = None,
    low_stock_threshold: int | None = None,
) -> Inventory:
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    if quantity_available < 0:
        raise ValidationError({'quantity_available': _('Quantity cannot be negative.')})

    if variant is not None:
        if variant.listing_id != listing.id:
            raise ValidationError(_('Variant does not belong to this listing.'))
        inventory, _ = Inventory.objects.select_for_update().get_or_create(
            listing=listing,
            variant=variant,
            defaults={'quantity_available': 0},
        )
    else:
        inventory = Inventory.objects.select_for_update().get(listing=listing, variant__isnull=True)

    inventory.quantity_available = int(quantity_available)
    if low_stock_threshold is not None:
        inventory.low_stock_threshold = max(0, int(low_stock_threshold))
    if inventory.available_to_sell > inventory.low_stock_threshold:
        inventory.low_stock_alert_sent = False
    inventory.save()

    # Reflect stock on public status when already published.
    if listing.status in {ListingStatus.ACTIVE, ListingStatus.SOLD_OUT}:
        rows = list(Inventory.objects.filter(listing=listing).select_related('variant'))
        has_stock = any(row.available_to_sell > 0 and (row.variant_id is None or row.variant.is_active) for row in rows)
        if not has_stock:
            listing.status = ListingStatus.SOLD_OUT
        elif listing.status == ListingStatus.SOLD_OUT:
            listing.status = ListingStatus.ACTIVE
        listing.save(update_fields=['status', 'updated_at'])

    _audit_listing(actor=actor, listing=listing, action='inventory.updated', description=f'Updated inventory for “{listing.title}”.')

    return inventory


@transaction.atomic
def add_listing_image(
    *,
    actor,
    listing: Listing,
    image,
    alt_text: str = '',
    position: int | None = None,
) -> ListingImage:
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    if position is None:
        last = listing.images.order_by('-position').first()
        position = (last.position + 1) if last else 0
    return ListingImage.objects.create(
        listing=listing,
        image=image,
        alt_text=(alt_text or listing.title)[:200],
        position=position,
    )


@transaction.atomic
def add_digital_asset(*, actor, listing, title, file, version=''):
    """Attach a private digital file to a digital listing.

    Allowed types: PDF, ZIP, JPEG, PNG, WebP (max 50 MB). Content is checked
    against declared MIME type via magic-byte signatures.
    """
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    if listing.product_type != ProductType.DIGITAL:
        raise ValidationError(_('Digital files can only be attached to digital listings.'))
    if file is None:
        raise ValidationError(_('Choose a digital asset file.'))
    if file.size > MAX_DIGITAL_ASSET_SIZE:
        raise ValidationError(_('Digital asset files must be 50 MB or smaller.'))
    content_type = (getattr(file, 'content_type', '') or '').lower()
    if content_type not in ALLOWED_DIGITAL_ASSET_TYPES:
        raise ValidationError(_('Upload a JPG, PNG, WebP, PDF, or ZIP file.'))
    if not _digital_asset_signature_matches(file, content_type):
        raise ValidationError(_('The file contents do not match its file type.'))
    return DigitalAsset.objects.create(listing=listing, title=title.strip(), file=file, version=version.strip())


@transaction.atomic
def add_listing_variant(
    *,
    actor,
    listing: Listing,
    name: str,
    sku: str = '',
    price_override=None,
    quantity_available: int = 0,
    option_values=None,
    cover_image=None,
) -> ListingVariant:
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    name = (name or '').strip()
    if not name:
        raise ValidationError({'name': _('Variant name is required.')})
    option_values = list(option_values or [])
    groups = [value.option_id for value in option_values]
    if len(groups) != len(set(groups)) or any(value.option.listing_id != listing.id for value in option_values):
        raise ValidationError(_('Choose at most one value from each option group on this listing.'))
    if cover_image and cover_image.listing_id != listing.id:
        raise ValidationError(_('Variant image must belong to this listing.'))
    summary = {value.option.name: value.value for value in option_values}
    variant = ListingVariant.objects.create(
        listing=listing,
        name=name or ' / '.join(summary.values()),
        sku=(sku or '').strip(),
        price_override=price_override,
        cover_image=cover_image,
        option_summary=summary,
    )
    variant.selected_values.set(option_values)
    Inventory.objects.create(
        listing=listing,
        variant=variant,
        quantity_available=max(0, int(quantity_available)),
    )
    return variant


@transaction.atomic
def add_listing_option(*, actor, listing, name: str, values: str):
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    clean_values = list(dict.fromkeys(value.strip() for value in values.split(',') if value.strip()))
    if not name.strip() or not clean_values:
        raise ValidationError(_('Option name and at least one value are required.'))
    option = ListingOption.objects.create(listing=listing, name=name.strip())
    ListingOptionValue.objects.bulk_create([
        ListingOptionValue(option=option, value=value, position=position)
        for position, value in enumerate(clean_values)
    ])
    return option


@transaction.atomic
def add_personalization_field(*, actor, listing, label: str, instructions: str = '', field_type: str = 'text', options: str = '', is_required: bool = False, max_length: int = 120):
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    choices = list(dict.fromkeys(value.strip() for value in options.split(',') if value.strip()))
    if field_type == PersonalizationFieldType.SELECT and not choices:
        raise ValidationError(_('Choice-list fields require at least one option.'))
    field = PersonalizationField.objects.create(
        listing=listing, label=label.strip(), instructions=instructions.strip(), field_type=field_type,
        options=choices, is_required=is_required, max_length=max_length,
        position=listing.personalization_fields.count(),
    )
    if not listing.is_personalizable:
        listing.is_personalizable = True
        listing.save(update_fields=['is_personalizable', 'updated_at'])
    return field


@transaction.atomic
def set_listing_attribute(*, actor, listing: Listing, name: str, value: str, position: int = 0):
    ensure_actor_can_manage_listing(actor=actor, listing=listing)
    name = (name or '').strip()
    value = (value or '').strip()
    if not name or not value:
        raise ValidationError(_('Attribute name and value are required.'))
    attr, _ = ListingAttribute.objects.update_or_create(
        listing=listing,
        name=name,
        defaults={'value': value, 'position': position},
    )
    return attr
