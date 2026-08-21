from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.services import add_digital_asset, create_listing
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'
PNG_BYTES = b'\x89PNG\r\n\x1a\n digital asset'
PDF_BYTES = b'%PDF-1.4 digital asset'
ZIP_BYTES = b'PK\x03\x04 digital asset'
MAX_DIGITAL_ASSET_SIZE = 50 * 1024 * 1024


@pytest.fixture
def seller(db):
    return User.objects.create_user(email='asset-seller@ziuza.co.ke', password=PASSWORD, display_name='Seller')


@pytest.fixture
def shop(seller):
    return create_shop(actor=seller, name='Digital Studio', county='Nairobi')


@pytest.fixture
def category(db):
    return Category.objects.create(name='Digital Goods', slug='digital-goods', is_visible=True)


@pytest.fixture
def digital_listing(seller, shop, category):
    return create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title='Printable Planner',
        base_price=Decimal('500.00'),
        product_type='digital',
        quantity_available=0,
    )


@pytest.mark.django_db
def test_digital_asset_rejects_mismatched_magic_bytes(digital_listing, seller):
    with pytest.raises(ValidationError, match='do not match'):
        add_digital_asset(
            actor=seller,
            listing=digital_listing,
            title='Spoofed PDF',
            file=SimpleUploadedFile('spoofed.pdf', PNG_BYTES, content_type='application/pdf'),
        )


@pytest.mark.django_db
def test_digital_asset_rejects_disallowed_content_type(digital_listing, seller):
    with pytest.raises(ValidationError, match='PDF'):
        add_digital_asset(
            actor=seller,
            listing=digital_listing,
            title='Executable',
            file=SimpleUploadedFile('payload.exe', b'MZ executable', content_type='application/octet-stream'),
        )


@pytest.mark.django_db
def test_digital_asset_rejects_oversized_file(digital_listing, seller):
    with pytest.raises(ValidationError, match='50 MB'):
        add_digital_asset(
            actor=seller,
            listing=digital_listing,
            title='Huge PDF',
            file=SimpleUploadedFile(
                'huge.pdf',
                PDF_BYTES + (b'0' * (MAX_DIGITAL_ASSET_SIZE - len(PDF_BYTES) + 1)),
                content_type='application/pdf',
            ),
        )


@pytest.mark.django_db
def test_digital_asset_accepts_allowed_types(digital_listing, seller):
    uploads = [
        ('guide.pdf', PDF_BYTES, 'application/pdf'),
        ('bundle.zip', ZIP_BYTES, 'application/zip'),
        ('cover.png', PNG_BYTES, 'image/png'),
        ('photo.jpg', b'\xff\xd8\xff jpeg asset', 'image/jpeg'),
        ('preview.webp', b'RIFF\x00\x00\x00\x00WEBP asset', 'image/webp'),
    ]
    created = []
    try:
        for name, payload, content_type in uploads:
            asset = add_digital_asset(
                actor=seller,
                listing=digital_listing,
                title=name,
                file=SimpleUploadedFile(name, payload, content_type=content_type),
            )
            created.append(asset)
        assert len(created) == len(uploads)
    finally:
        for asset in created:
            asset.file.delete(save=False)


@pytest.mark.django_db
def test_digital_asset_download_and_x_accel_redirect(client, digital_listing, seller, settings):
    from django.urls import reverse

    from apps.marketplace.orders.models import DownloadGrant, Order, OrderItem, SellerOrder
    from apps.marketplace.orders.services import _public_number

    buyer = User.objects.create_user(email='buyer-download@ziuza.co.ke', password=PASSWORD)
    asset = add_digital_asset(
        actor=seller,
        listing=digital_listing,
        title='Planner PDF',
        file=SimpleUploadedFile('test_planner.pdf', PDF_BYTES, content_type='application/pdf'),
    )
    try:
        order = Order.objects.create(
            public_number=_public_number(),
            buyer=buyer,
            subtotal=Decimal('500.00'),
            grand_total=Decimal('500.00'),
            payment_status='paid',
        )
        seller_order = SellerOrder.objects.create(
            order=order,
            shop=digital_listing.shop,
            subtotal=Decimal('500.00'),
        )
        item = OrderItem.objects.create(
            order=order,
            seller_order=seller_order,
            shop=digital_listing.shop,
            listing_id=digital_listing.id,
            title_snapshot=digital_listing.title,
            quantity=1,
            unit_price=Decimal('500.00'),
            line_total=Decimal('500.00'),
            product_type_snapshot='digital',
        )
        grant = DownloadGrant.objects.create(order_item=item, buyer=buyer, is_active=True)

        client.force_login(buyer)
        url = reverse('orders:download_asset', kwargs={'grant_id': grant.id, 'asset_id': asset.id})

        expected_name = Path(asset.file.name).name

        # Default: FileResponse
        settings.USE_X_ACCEL_REDIRECT = False
        res = client.get(url)
        assert res.status_code == 200
        assert f'attachment; filename="{expected_name}"' in res['Content-Disposition']
        res.close()

        # Enabled X-Accel-Redirect
        settings.USE_X_ACCEL_REDIRECT = True
        settings.X_ACCEL_REDIRECT_PREFIX = '/protected_media/'
        res2 = client.get(url)
        assert res2.status_code == 200
        assert 'X-Accel-Redirect' in res2
        assert res2['X-Accel-Redirect'].startswith('/protected_media/')
        assert f'attachment; filename="{expected_name}"' in res2['Content-Disposition']
        res2.close()
    finally:
        asset.file.delete(save=False)
