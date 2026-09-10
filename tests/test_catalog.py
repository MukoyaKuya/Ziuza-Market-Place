import csv
import io
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.bulk import CATALOG_COLUMNS, import_catalog_csv
from apps.marketplace.listings.models import BulkOperationStatus, Inventory, Listing, ListingStatus
from apps.marketplace.listings.services import (
    create_listing,
    pause_listing,
    publish_listing,
    set_inventory_quantity,
)
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


def catalogue_upload(*rows, name='catalogue.csv'):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=CATALOG_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return SimpleUploadedFile(name, stream.getvalue().encode('utf-8'), content_type='text/csv')


def catalogue_row(**overrides):
    row = {
        'slug': '',
        'title': 'New woven basket',
        'category_slug': 'fashion',
        'product_type': 'physical',
        'base_price': '1200.00',
        'currency': 'KES',
        'sku': 'BASKET-NEW',
        'quantity_available': '7',
        'low_stock_threshold': '2',
        'short_description': 'A sturdy basket',
        'description': 'Handwoven in Kenya',
    }
    row.update(overrides)
    return row


@pytest.fixture
def user(db):
    return User.objects.create_user(email='maker@ziuza.co.ke', password=PASSWORD, display_name='Maker')


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email='other@ziuza.co.ke', password=PASSWORD, display_name='Other')


@pytest.fixture
def category(db):
    return Category.objects.create(name='Fashion', slug='fashion', is_visible=True)


@pytest.fixture
def shop(user):
    return create_shop(actor=user, name='Coastal Kikoy Co', county='Mombasa')


@pytest.fixture
def listing(user, shop, category):
    return create_listing(
        actor=user,
        shop=shop,
        category=category,
        title='Handwoven Kikoy Wrap',
        base_price=Decimal('1650.00'),
        quantity_available=5,
        description='Pure cotton coastal wrap',
    )


@pytest.mark.django_db
def test_seed_categories_command(django_user_model):
    from django.core.management import call_command

    call_command('seed_categories')
    assert Category.objects.filter(slug='fashion').exists()
    assert Category.objects.filter(slug='fashion-women', parent__slug='fashion').exists()


def test_category_uses_admin_uploaded_image_for_card_artwork():
    category = Category(
        name='Custom category',
        slug='custom-category',
        image='categories/custom-category.jpg',
    )

    assert category.get_icon_url.endswith('/categories/custom-category.jpg')


@pytest.mark.django_db
def test_create_and_publish_listing(client, user, shop, category, listing):
    client.force_login(user)
    publish_listing(actor=user, listing=listing)
    listing.refresh_from_db()
    assert listing.status == ListingStatus.ACTIVE
    assert listing.published_at is not None

    response = client.get(reverse('listings:detail', kwargs={'slug': listing.slug}))
    assert response.status_code == 200
    assert b'Handwoven Kikoy Wrap' in response.content
    assert b'Coastal Kikoy Co' in response.content


@pytest.mark.django_db
def test_listing_without_uploaded_images_renders_category_feature_image(client, user, shop):
    jewelry = Category.objects.create(name='Jewelry', slug='jewelry', is_visible=True)
    necklace = create_listing(
        actor=user,
        shop=shop,
        category=jewelry,
        title='Maasai Bead Necklace',
        base_price=Decimal('1200.00'),
        quantity_available=8,
        description='Traditional Kenyan beadwork.',
    )
    publish_listing(actor=user, listing=necklace)

    response = client.get(reverse('listings:detail', kwargs={'slug': necklace.slug}))

    assert response.status_code == 200
    assert response.context['cover'] is None
    assert response.context['featured_image_is_fallback'] is True
    assert response.context['featured_image_url'].endswith('/static/images/categories/jewelry.png')
    assert b'data-featured-product-image' in response.content
    assert b'/static/images/categories/jewelry.png' in response.content
    assert b'<meta property="og:image"' in response.content


@pytest.mark.django_db
def test_draft_listing_not_public(client, listing):
    response = client.get(reverse('listings:detail', kwargs={'slug': listing.slug}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_seller_cannot_edit_other_shop_listing(user, other_user, category, listing):
    other_shop = create_shop(actor=other_user, name='Other Shop', county='Nairobi')
    with pytest.raises(PermissionDenied):
        create_listing(
            actor=other_user,
            shop=listing.shop,
            category=category,
            title='Nope',
            base_price=Decimal('10.00'),
        )
    # other seller managing their own shop is fine
    create_listing(
        actor=other_user,
        shop=other_shop,
        category=category,
        title='Own listing',
        base_price=Decimal('10.00'),
    )


@pytest.mark.django_db
def test_seller_listing_list_and_create_flow(client, user, shop, category):
    client.force_login(user)
    response = client.get(reverse('listings:seller_list'))
    assert response.status_code == 200

    create_response = client.post(
        reverse('listings:seller_create'),
        {
            'title': 'Sisal Kiondo',
            'category': str(category.id),
            'short_description': 'Market basket',
            'description': 'Handwoven',
            'base_price': '2800.00',
            'currency': 'USD',
            'sku': 'KION-1',
            'quantity_available': '4',
        },
    )
    assert create_response.status_code == 302
    listing = Listing.objects.get(title='Sisal Kiondo')
    assert listing.status == ListingStatus.DRAFT
    assert listing.shop_id == shop.id
    assert listing.currency == 'KES'


@pytest.mark.django_db
def test_inventory_updates_sold_out_status(user, listing):
    publish_listing(actor=user, listing=listing)
    set_inventory_quantity(actor=user, listing=listing, quantity_available=0)
    listing.refresh_from_db()
    assert listing.status == ListingStatus.SOLD_OUT

    set_inventory_quantity(actor=user, listing=listing, quantity_available=3)
    listing.refresh_from_db()
    assert listing.status == ListingStatus.ACTIVE


@pytest.mark.django_db
def test_inventory_cannot_be_reduced_below_reserved_quantity(user, listing):
    inventory = Inventory.objects.get(listing=listing, variant__isnull=True)
    inventory.quantity_reserved = 3
    inventory.save(update_fields=['quantity_reserved', 'updated_at'])

    with pytest.raises(ValidationError, match='reserved by pending orders'):
        set_inventory_quantity(actor=user, listing=listing, quantity_available=2)

    inventory.refresh_from_db()
    assert inventory.quantity_available == 5
    assert inventory.quantity_reserved == 3


@pytest.mark.django_db
def test_pause_listing(user, listing):
    publish_listing(actor=user, listing=listing)
    pause_listing(actor=user, listing=listing)
    listing.refresh_from_db()
    assert listing.status == ListingStatus.PAUSED
    with pytest.raises(ValidationError):
        pause_listing(actor=user, listing=listing)


@pytest.mark.django_db
def test_category_page_lists_active_only(client, user, shop, category, listing):
    publish_listing(actor=user, listing=listing)
    draft = create_listing(
        actor=user,
        shop=shop,
        category=category,
        title='Hidden Draft',
        base_price=Decimal('100.00'),
        quantity_available=1,
    )
    response = client.get(reverse('listings:category_detail', kwargs={'slug': category.slug}))
    assert response.status_code == 200
    assert b'Handwoven Kikoy Wrap' in response.content
    assert b'Hidden Draft' not in response.content
    assert draft.status == ListingStatus.DRAFT


@pytest.mark.django_db
def test_other_user_cannot_publish_via_http(client, other_user, listing):
    create_shop(actor=other_user, name='Rival Shop', county='Nairobi')
    client.force_login(other_user)
    response = client.post(reverse('listings:seller_publish', kwargs={'listing_id': listing.id}))
    assert response.status_code == 404
    listing.refresh_from_db()
    assert listing.status == ListingStatus.DRAFT


@pytest.mark.django_db
def test_bulk_import_dry_run_makes_no_catalogue_changes(user, shop, category):
    operation = import_catalog_csv(
        actor=user,
        shop=shop,
        uploaded_file=catalogue_upload(catalogue_row()),
        dry_run=True,
    )

    assert operation.status == BulkOperationStatus.VALIDATED
    assert operation.created_rows == 1
    assert not Listing.objects.filter(shop=shop, sku='BASKET-NEW').exists()


@pytest.mark.django_db
def test_bulk_import_rejects_every_row_when_one_row_is_invalid(user, shop, category):
    operation = import_catalog_csv(
        actor=user,
        shop=shop,
        uploaded_file=catalogue_upload(
            catalogue_row(sku='VALID-ROW'),
            catalogue_row(title='Broken row', sku='BROKEN-ROW', category_slug='missing-category'),
        ),
        dry_run=False,
    )

    assert operation.status == BulkOperationStatus.FAILED
    assert operation.error_count == 1
    assert not Listing.objects.filter(shop=shop, sku__in=['VALID-ROW', 'BROKEN-ROW']).exists()


@pytest.mark.django_db
def test_bulk_import_updates_price_and_inventory_for_own_listing(user, shop, category, listing):
    operation = import_catalog_csv(
        actor=user,
        shop=shop,
        uploaded_file=catalogue_upload(catalogue_row(
            slug=listing.slug,
            title=listing.title,
            sku='KIKOY-UPDATED',
            base_price='1999.50',
            quantity_available='14',
            low_stock_threshold='4',
        )),
        dry_run=False,
    )

    listing.refresh_from_db()
    inventory = listing.inventory_rows.get(variant__isnull=True)
    assert operation.status == BulkOperationStatus.COMPLETED
    assert operation.updated_rows == 1
    assert listing.base_price == Decimal('1999.50')
    assert listing.sku == 'KIKOY-UPDATED'
    assert inventory.quantity_available == 14
    assert inventory.low_stock_threshold == 4


@pytest.mark.django_db
def test_bulk_import_cannot_target_another_shops_slug(user, other_user, shop, category):
    other_shop = create_shop(actor=other_user, name='Other Catalogue', county='Nairobi')
    other_listing = create_listing(
        actor=other_user,
        shop=other_shop,
        category=category,
        title='Other seller item',
        base_price=Decimal('500.00'),
        quantity_available=3,
    )
    operation = import_catalog_csv(
        actor=user,
        shop=shop,
        uploaded_file=catalogue_upload(catalogue_row(slug=other_listing.slug, base_price='1.00')),
        dry_run=False,
    )

    other_listing.refresh_from_db()
    assert operation.status == BulkOperationStatus.FAILED
    assert other_listing.base_price == Decimal('500.00')


@pytest.mark.django_db
def test_bulk_export_prevents_spreadsheet_formula_execution(client, user, shop, listing):
    listing.title = '=HYPERLINK("https://example.invalid")'
    listing.sku = '+CMD'
    listing.save(update_fields=['title', 'sku', 'updated_at'])
    client.force_login(user)

    response = client.get(reverse('listings:seller_bulk_export'))
    exported = next(csv.DictReader(io.StringIO(response.content.decode('utf-8'))))

    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/csv')
    assert exported['title'].startswith("'=")
    assert exported['sku'].startswith("'+")
