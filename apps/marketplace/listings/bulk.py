import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import (
    BulkOperation,
    BulkOperationStatus,
    BulkOperationType,
    Inventory,
    Listing,
    ListingStatus,
    ProductType,
)
from apps.marketplace.listings.services import create_listing, set_inventory_quantity, update_listing
from apps.marketplace.shops.permissions import MANAGE_LISTINGS, ensure_shop_permission


MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 500
CATALOG_COLUMNS = (
    'slug',
    'title',
    'category_slug',
    'product_type',
    'base_price',
    'currency',
    'sku',
    'quantity_available',
    'low_stock_threshold',
    'short_description',
    'description',
)
REQUIRED_COLUMNS = set(CATALOG_COLUMNS)
FORMULA_PREFIXES = ('=', '+', '-', '@')


@dataclass(frozen=True)
class PreparedRow:
    row_number: int
    listing_id: object | None
    title: str
    category: Category
    product_type: str
    base_price: Decimal
    currency: str
    sku: str
    quantity_available: int
    low_stock_threshold: int
    short_description: str
    description: str


def _safe_spreadsheet_text(value) -> str:
    text = str(value or '')
    if text.lstrip().startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def export_catalog_csv(*, actor, shop) -> tuple[str, BulkOperation]:
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_LISTINGS)
    base_inventory = Inventory.objects.filter(variant__isnull=True)
    listings = Listing.objects.filter(shop=shop).select_related('category').prefetch_related(
        Prefetch('inventory_rows', queryset=base_inventory, to_attr='bulk_base_inventory')
    ).order_by('title')

    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=CATALOG_COLUMNS)
    writer.writeheader()
    total = 0
    for listing in listings:
        inventory = listing.bulk_base_inventory[0] if listing.bulk_base_inventory else None
        writer.writerow({
            'slug': _safe_spreadsheet_text(listing.slug),
            'title': _safe_spreadsheet_text(listing.title),
            'category_slug': _safe_spreadsheet_text(listing.category.slug),
            'product_type': listing.product_type,
            'base_price': str(listing.base_price),
            'currency': _safe_spreadsheet_text(listing.currency),
            'sku': _safe_spreadsheet_text(listing.sku),
            'quantity_available': inventory.quantity_available if inventory else 0,
            'low_stock_threshold': inventory.low_stock_threshold if inventory else 3,
            'short_description': _safe_spreadsheet_text(listing.short_description),
            'description': _safe_spreadsheet_text(listing.description),
        })
        total += 1

    operation = BulkOperation.objects.create(
        shop=shop,
        actor=actor,
        operation=BulkOperationType.CATALOG_EXPORT,
        status=BulkOperationStatus.COMPLETED,
        file_name='ziuza-catalogue.csv',
        total_rows=total,
        summary={'message': f'Exported {total} catalogue row(s).'},
    )
    return output.getvalue(), operation


def _error(row_number: int | None, message: str) -> dict:
    return {'row': row_number, 'message': message}


def _read_csv(uploaded_file) -> tuple[list[dict], list[dict]]:
    if not uploaded_file:
        return [], [_error(None, 'Choose a CSV file to upload.')]
    if getattr(uploaded_file, 'size', 0) > MAX_IMPORT_BYTES:
        return [], [_error(None, 'The CSV file must be 2 MB or smaller.')]
    raw = uploaded_file.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        return [], [_error(None, 'The CSV file must be 2 MB or smaller.')]
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return [], [_error(None, 'Save the CSV using UTF-8 encoding and try again.')]
    try:
        reader = csv.DictReader(io.StringIO(text, newline=''))
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            return [], [_error(None, 'The CSV contains duplicate column names.')]
        missing = sorted(REQUIRED_COLUMNS - set(headers))
        unexpected = sorted(set(headers) - REQUIRED_COLUMNS)
        if missing:
            return [], [_error(None, f"Missing column(s): {', '.join(missing)}.")]
        if unexpected:
            return [], [_error(None, f"Unknown column(s): {', '.join(unexpected)}.")]
        rows = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                return [], [_error(row_number, 'This row has more values than the header.')]
            if not any((value or '').strip() for value in row.values()):
                continue
            rows.append({'row_number': row_number, **row})
            if len(rows) > MAX_IMPORT_ROWS:
                return [], [_error(None, f'Imports are limited to {MAX_IMPORT_ROWS} data rows.')]
        if not rows:
            return [], [_error(None, 'The CSV has no data rows.')]
        return rows, []
    except csv.Error:
        return [], [_error(None, 'The CSV could not be read. Check its formatting and try again.')]


def _parse_decimal(value: str, row_number: int, errors: list[dict]) -> Decimal | None:
    try:
        amount = Decimal((value or '').strip())
    except (InvalidOperation, ValueError):
        errors.append(_error(row_number, 'base_price must be a valid number.'))
        return None
    if amount <= 0 or amount.as_tuple().exponent < -2 or amount > Decimal('9999999999.99'):
        errors.append(_error(row_number, 'base_price must be positive, use at most 2 decimals, and fit the supported range.'))
        return None
    return amount


def _parse_integer(value: str, field: str, row_number: int, errors: list[dict]) -> int | None:
    try:
        parsed = int((value or '').strip())
    except (TypeError, ValueError):
        errors.append(_error(row_number, f'{field} must be a whole number.'))
        return None
    if parsed < 0 or parsed > 2_147_483_647:
        errors.append(_error(row_number, f'{field} must be between 0 and 2147483647.'))
        return None
    return parsed


def _prepare_rows(*, shop, raw_rows: list[dict]) -> tuple[list[PreparedRow], list[dict]]:
    errors = []
    prepared = []
    categories = {category.slug: category for category in Category.objects.filter(is_visible=True)}
    shop_listings = list(Listing.objects.filter(shop=shop))
    by_slug = {listing.slug: listing for listing in shop_listings}
    by_sku = {}
    for listing in shop_listings:
        if listing.sku:
            by_sku.setdefault(listing.sku.casefold(), []).append(listing)
    foreign_slugs = set(
        Listing.objects.filter(slug__in=[(row.get('slug') or '').strip() for row in raw_rows])
        .exclude(shop=shop)
        .values_list('slug', flat=True)
    )
    seen_targets = set()
    seen_new_skus = set()

    for row in raw_rows:
        row_number = row['row_number']
        start_error_count = len(errors)
        slug = (row.get('slug') or '').strip()
        title = (row.get('title') or '').strip()
        category_slug = (row.get('category_slug') or '').strip()
        product_type = (row.get('product_type') or '').strip()
        currency = (row.get('currency') or '').strip().upper()
        sku = (row.get('sku') or '').strip()
        short_description = (row.get('short_description') or '').strip()
        description = (row.get('description') or '').strip()

        if not title or len(title) > 200:
            errors.append(_error(row_number, 'title is required and must be 200 characters or fewer.'))
        category = categories.get(category_slug)
        if category is None:
            errors.append(_error(row_number, 'category_slug must identify a visible category.'))
        if product_type not in ProductType.values:
            errors.append(_error(row_number, f"product_type must be one of: {', '.join(ProductType.values)}."))
        if len(currency) != 3 or not currency.isalpha():
            errors.append(_error(row_number, 'currency must be a 3-letter code such as KES.'))
        if len(sku) > 64:
            errors.append(_error(row_number, 'sku must be 64 characters or fewer.'))
        if len(short_description) > 300:
            errors.append(_error(row_number, 'short_description must be 300 characters or fewer.'))
        amount = _parse_decimal(row.get('base_price'), row_number, errors)
        quantity = _parse_integer(row.get('quantity_available'), 'quantity_available', row_number, errors)
        threshold = _parse_integer(row.get('low_stock_threshold'), 'low_stock_threshold', row_number, errors)

        listing = None
        if slug:
            listing = by_slug.get(slug)
            if listing is None:
                message = 'This slug belongs to another shop and cannot be changed.' if slug in foreign_slugs else 'Unknown slug. Leave slug blank to create a new listing.'
                errors.append(_error(row_number, message))
        elif sku:
            matches = by_sku.get(sku.casefold(), [])
            if len(matches) == 1:
                listing = matches[0]
            elif len(matches) > 1:
                errors.append(_error(row_number, 'This SKU matches multiple listings in your shop; use a slug instead.'))

        if listing and listing.status == ListingStatus.ARCHIVED:
            errors.append(_error(row_number, 'Archived listings cannot be updated by import.'))
        target_key = f'listing:{listing.pk}' if listing else f'new:{row_number}'
        if target_key in seen_targets:
            errors.append(_error(row_number, 'The same listing appears more than once in this file.'))
        seen_targets.add(target_key)
        if not listing and sku:
            sku_key = sku.casefold()
            if sku_key in seen_new_skus:
                errors.append(_error(row_number, 'The same new SKU appears more than once in this file.'))
            seen_new_skus.add(sku_key)

        if len(errors) == start_error_count:
            prepared.append(PreparedRow(
                row_number=row_number,
                listing_id=listing.pk if listing else None,
                title=title,
                category=category,
                product_type=product_type,
                base_price=amount,
                currency=currency,
                sku=sku,
                quantity_available=quantity,
                low_stock_threshold=threshold,
                short_description=short_description,
                description=description,
            ))
    return prepared, errors


def import_catalog_csv(*, actor, shop, uploaded_file, dry_run: bool = True) -> BulkOperation:
    ensure_shop_permission(actor=actor, shop=shop, permission=MANAGE_LISTINGS)
    file_name = str(getattr(uploaded_file, 'name', ''))[:255]
    raw_rows, errors = _read_csv(uploaded_file)
    prepared = []
    if not errors:
        prepared, errors = _prepare_rows(shop=shop, raw_rows=raw_rows)

    if errors:
        return BulkOperation.objects.create(
            shop=shop,
            actor=actor,
            operation=BulkOperationType.CATALOG_IMPORT,
            status=BulkOperationStatus.FAILED,
            file_name=file_name,
            dry_run=dry_run,
            total_rows=len(raw_rows),
            error_count=len(errors),
            summary={'errors': errors},
        )

    create_count = sum(row.listing_id is None for row in prepared)
    update_count = len(prepared) - create_count
    operation = BulkOperation.objects.create(
        shop=shop,
        actor=actor,
        operation=BulkOperationType.CATALOG_IMPORT,
        status=BulkOperationStatus.VALIDATED if dry_run else BulkOperationStatus.FAILED,
        file_name=file_name,
        dry_run=dry_run,
        total_rows=len(prepared),
        created_rows=create_count,
        updated_rows=update_count,
        summary={'message': f'{len(prepared)} row(s) passed validation. No changes were made.'} if dry_run else {},
    )
    if dry_run:
        return operation

    try:
        with transaction.atomic():
            for row in prepared:
                if row.listing_id is None:
                    listing = create_listing(
                        actor=actor,
                        shop=shop,
                        category=row.category,
                        title=row.title,
                        base_price=row.base_price,
                        currency=row.currency,
                        short_description=row.short_description,
                        description=row.description,
                        sku=row.sku,
                        quantity_available=row.quantity_available,
                        product_type=row.product_type,
                    )
                    set_inventory_quantity(
                        actor=actor,
                        listing=listing,
                        quantity_available=row.quantity_available,
                        low_stock_threshold=row.low_stock_threshold,
                    )
                else:
                    listing = Listing.objects.select_for_update().get(pk=row.listing_id, shop=shop)
                    update_listing(
                        actor=actor,
                        listing=listing,
                        title=row.title,
                        category=row.category,
                        base_price=row.base_price,
                        currency=row.currency,
                        short_description=row.short_description,
                        description=row.description,
                        sku=row.sku,
                        product_type=row.product_type,
                    )
                    set_inventory_quantity(
                        actor=actor,
                        listing=listing,
                        quantity_available=row.quantity_available,
                        low_stock_threshold=row.low_stock_threshold,
                    )
            operation.status = BulkOperationStatus.COMPLETED
            operation.summary = {'message': f'Applied {len(prepared)} catalogue row(s).'}
            operation.save(update_fields=['status', 'summary'])
    except Exception:
        operation.status = BulkOperationStatus.FAILED
        operation.error_count = 1
        operation.summary = {'errors': [_error(None, 'The import was rolled back; no catalogue changes were saved.')]}
        operation.save(update_fields=['status', 'error_count', 'summary'])
        raise
    return operation
