import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.marketplace.cart.services import add_to_cart, get_or_create_cart
from apps.marketplace.categories.models import Category
from apps.marketplace.favorites.services import toggle_favorite
from apps.marketplace.listings.models import Inventory
from apps.marketplace.listings.services import (
    add_listing_option,
    add_listing_variant,
    add_personalization_field,
    create_listing,
    publish_listing,
)
from apps.marketplace.orders.models import FulfillmentStatus, HelpRequestStatus, Order, PaymentStatus
from apps.marketplace.orders.services import create_checkout_order, expire_stale_orders, release_order_inventory
from apps.marketplace.orders.support import open_help_request, seller_respond_to_help_request
from apps.marketplace.payments.models import PaymentStatusChoice
from apps.marketplace.payments.providers import get_provider
from apps.marketplace.promotions.models import DiscountType, Promotion, RedemptionStatus
from apps.marketplace.reviews.models import Review, create_review
from apps.marketplace.shipping.models import ShipmentEvent, update_seller_fulfillment
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def seller(db):
    return User.objects.create_user(email='seller@ziuza.co.ke', password=PASSWORD, display_name='Seller')


@pytest.fixture
def buyer(db):
    return User.objects.create_user(email='buyer@ziuza.co.ke', password=PASSWORD, display_name='Buyer')


@pytest.fixture
def category(db):
    return Category.objects.create(name='Fashion', slug='fashion', is_visible=True)


@pytest.fixture
def shop(seller):
    return create_shop(actor=seller, name='Kiondo Works', county='Nairobi')


@pytest.fixture
def listing(seller, shop, category):
    item = create_listing(
        actor=seller,
        shop=shop,
        category=category,
        title='Sisal Market Basket',
        base_price=Decimal('2500.00'),
        quantity_available=3,
        description='Handwoven sisal',
    )
    publish_listing(actor=seller, listing=item)
    return item


@pytest.fixture
def address(buyer):
    return Address.objects.create(
        user=buyer,
        recipient_name='Buyer Person',
        phone='0712345678',
        address_line_1='12 Ngong Road',
        city_or_town='Nairobi',
        county='Nairobi',
        country='Kenya',
        is_default_shipping=True,
    )


@pytest.mark.django_db
def test_search_finds_published_listing(client, listing):
    response = client.get(reverse('search:results'), {'q': 'Sisal'})
    assert response.status_code == 200
    assert b'Sisal Market Basket' in response.content


@pytest.mark.django_db
def test_favorite_toggle(buyer, listing):
    favorited, fav = toggle_favorite(actor=buyer, listing=listing)
    assert favorited is True
    assert fav is not None
    favorited, fav = toggle_favorite(actor=buyer, listing=listing)
    assert favorited is False
    assert fav is None


@pytest.mark.django_db
def test_commerce_flow_cart_checkout_pay_review(client, buyer, seller, listing, address):
    rf = RequestFactory()
    req = rf.get('/')
    req.user = buyer
    req.session = client.session
    req.session.save()

    add_to_cart(request=req, listing=listing, quantity=1)
    cart = get_or_create_cart(request=req)
    assert cart.items.count() == 1

    order = create_checkout_order(
        actor=buyer,
        cart=cart,
        shipping_address=address,
        shipping_method_code='standard',
        shipping_fee=Decimal('300.00'),
    )
    assert order.payment_status == PaymentStatus.PENDING
    inv = Inventory.objects.get(listing=listing, variant__isnull=True)
    assert inv.quantity_reserved == 1

    provider = get_provider('fake')
    payment = provider.initiate_payment(order=order)
    payment = provider.process_callback(
        payload={
            'provider_reference': payment.provider_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
        }
    )
    assert payment.status == PaymentStatusChoice.CONFIRMED
    order.refresh_from_db()
    assert order.payment_status == PaymentStatus.PAID
    inv.refresh_from_db()
    assert inv.quantity_available == 2
    assert inv.quantity_reserved == 0

    seller_order = order.seller_orders.get()
    seller_order.fulfillment_status = FulfillmentStatus.DELIVERED
    seller_order.save(update_fields=['fulfillment_status', 'updated_at'])
    item = order.items.get()
    review = create_review(actor=buyer, order_item=item, rating=5, title='Beautiful', body='Worth it')
    assert Review.objects.filter(id=review.id, listing=listing).exists()

    client.force_login(seller)
    response = client.get(reverse('analytics:seller'))
    assert response.status_code == 200
    assert Order.objects.filter(buyer=buyer, payment_status=PaymentStatus.PAID).exists()

    overview = client.get(reverse('shops:dashboard'))
    assert overview.status_code == 200
    assert b'Recent orders' in overview.content
    assert order.public_number.encode() in overview.content


@pytest.mark.django_db
def test_mpesa_provider_callback_idempotent(buyer, seller, listing, address):
    rf = RequestFactory()
    req = rf.get('/')
    req.user = buyer
    req.session = {}
    from django.contrib.sessions.backends.db import SessionStore

    req.session = SessionStore()
    req.session.create()
    add_to_cart(request=req, listing=listing, quantity=1)
    cart = get_or_create_cart(request=req)
    order = create_checkout_order(
        actor=buyer,
        cart=cart,
        shipping_address=address,
        shipping_method_code='pickup',
        shipping_fee=Decimal('0.00'),
    )
    provider = get_provider('mpesa')
    payment = provider.initiate_payment(order=order, phone='254712345678')
    assert payment.provider == 'mpesa'
    assert payment.status == PaymentStatusChoice.PENDING

    payload = {
        'provider_reference': payment.provider_reference,
        'CheckoutRequestID': payment.provider_reference,
        'amount': str(payment.amount),
        'currency': 'KES',
        'ResultCode': '0',
    }
    first = provider.process_callback(payload=payload)
    second = provider.process_callback(payload=payload)
    assert first.status == PaymentStatusChoice.CONFIRMED
    assert second.status == PaymentStatusChoice.CONFIRMED
    order.refresh_from_db()
    assert order.payment_status == PaymentStatus.PAID


@pytest.mark.django_db
def test_failed_payment_releases_reserved_inventory(client, buyer, listing, address):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    order = create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
    )
    payment = get_provider('fake').initiate_payment(order=order)
    get_provider('fake').process_callback(
        payload={
            'provider_reference': payment.provider_reference,
            'amount': '1.00',
            'currency': payment.currency,
        }
    )
    order.refresh_from_db()
    inventory = Inventory.objects.get(listing=listing, variant__isnull=True)
    assert order.payment_status == PaymentStatus.FAILED
    assert order.reservation_released_at is not None
    assert inventory.quantity_reserved == 0


@pytest.mark.django_db
def test_expired_order_release_is_idempotent(client, buyer, listing, address):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    order = create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
    )
    Order.objects.filter(pk=order.pk).update(reservation_expires_at=timezone.now())
    assert expire_stale_orders() == 1
    assert expire_stale_orders() == 0
    release_order_inventory(order=order)
    inventory = Inventory.objects.get(listing=listing, variant__isnull=True)
    assert inventory.quantity_reserved == 0


@pytest.mark.django_db
@override_settings(MPESA_LIVE=True, MPESA_CALLBACK_SECRET='')
def test_live_mpesa_rejects_unsigned_callback(client, buyer, listing, address):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    order = create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
    )
    payment = get_provider('mpesa').initiate_payment(order=order, phone='254712345678')
    with pytest.raises(ValueError, match='Invalid M-Pesa callback signature'):
        get_provider('mpesa').process_callback(
            payload={
                'provider_reference': payment.provider_reference,
                'amount': str(payment.amount),
                'currency': payment.currency,
                'ResultCode': '0',
            }
        )


@pytest.mark.django_db
def test_released_order_cannot_restart_payment(client, buyer, listing, address):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    order = create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
    )
    release_order_inventory(order=order)
    order.refresh_from_db()
    with pytest.raises(Exception, match='reservation has been released'):
        get_provider('fake').initiate_payment(order=order)


@pytest.mark.django_db
@override_settings(MPESA_LIVE=True, MPESA_CALLBACK_SECRET='callback-token')
def test_mpesa_callback_endpoint_requires_token_and_accepts_daraja_json(client, buyer, listing, address):
    rf = RequestFactory()
    request = rf.get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    order = create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
    )
    payment = get_provider('mpesa').initiate_payment(order=order, phone='254712345678')
    callback = {
        'Body': {
            'stkCallback': {
                'CheckoutRequestID': payment.provider_reference,
                'ResultCode': 0,
                'CallbackMetadata': {
                    'Item': [
                        {'Name': 'Amount', 'Value': float(payment.amount)},
                        {'Name': 'MpesaReceiptNumber', 'Value': 'TEST123'},
                    ]
                },
            }
        }
    }
    url = reverse('payments:mpesa_callback')
    rejected = client.post(url, data=json.dumps(callback), content_type='application/json')
    assert rejected.status_code == 400

    accepted = client.post(f'{url}?token=callback-token', data=json.dumps(callback), content_type='application/json')
    assert accepted.status_code == 200
    order.refresh_from_db()
    assert order.payment_status == PaymentStatus.PAID


def _paid_order(client, buyer, listing, address):
    request = RequestFactory().get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    order = create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
    )
    provider = get_provider('fake')
    payment = provider.initiate_payment(order=order)
    provider.process_callback(payload={
        'provider_reference': payment.provider_reference,
        'amount': str(payment.amount),
        'currency': payment.currency,
    })
    order.refresh_from_db()
    return order


@pytest.mark.django_db
def test_fulfillment_has_valid_transitions_tracking_timeline_and_buyer_notification(client, buyer, seller, listing, address):
    order = _paid_order(client, buyer, listing, address)
    seller_order = order.seller_orders.select_related('shop', 'order').get()
    update_seller_fulfillment(actor=seller, seller_order=seller_order, status=FulfillmentStatus.PROCESSING)
    update_seller_fulfillment(actor=seller, seller_order=seller_order, status=FulfillmentStatus.READY)
    update_seller_fulfillment(
        actor=seller,
        seller_order=seller_order,
        status=FulfillmentStatus.SHIPPED,
        carrier='Sendy',
        tracking_number='TRK-123',
        note='Parcel collected in Nairobi',
    )
    seller_order.refresh_from_db()
    order.refresh_from_db()
    shipment = seller_order.shipments.get()
    assert shipment.tracking_number == 'TRK-123'
    assert ShipmentEvent.objects.filter(shipment=shipment).count() == 3
    assert order.fulfillment_status == FulfillmentStatus.SHIPPED
    assert buyer.notifications.filter(type='shipment_update').count() == 3

    with pytest.raises(Exception, match='Cannot move'):
        update_seller_fulfillment(actor=seller, seller_order=seller_order, status=FulfillmentStatus.PROCESSING)


@pytest.mark.django_db
def test_buyer_help_request_and_seller_response_are_scoped_and_notified(client, buyer, seller, listing, address):
    order = _paid_order(client, buyer, listing, address)
    seller_order = order.seller_orders.select_related('shop__owner', 'order').get()
    case = open_help_request(
        actor=buyer,
        seller_order=seller_order,
        reason='not_received',
        description='The expected delivery date passed and nothing arrived.',
        desired_resolution='Please locate the parcel.',
    )
    assert case.status == HelpRequestStatus.OPEN
    assert seller.notifications.filter(type='help_request').exists()

    seller_respond_to_help_request(
        actor=seller,
        case=case,
        response='We contacted the courier and will update you tomorrow.',
    )
    case.refresh_from_db()
    assert case.status == HelpRequestStatus.SELLER_RESPONDED
    assert buyer.notifications.filter(type='help_request_response').exists()

    with pytest.raises(ValidationError):
        open_help_request(
            actor=buyer,
            seller_order=seller_order,
            reason='late',
            description='This second active request should not be permitted.',
        )


@pytest.mark.django_db
def test_coupon_discount_is_shop_scoped_and_redeemed_only_after_payment(client, buyer, listing, address):
    from datetime import timedelta

    promotion = Promotion.objects.create(
        shop=listing.shop,
        name='Welcome offer',
        code='welcome10',
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal('10.00'),
        minimum_spend=Decimal('1000.00'),
        usage_limit=10,
        per_user_limit=1,
        starts_at=timezone.now() - timedelta(minutes=1),
        ends_at=timezone.now() + timedelta(days=7),
    )
    request = RequestFactory().get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    order = create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
        coupon_code='WELCOME10',
    )
    assert order.discount_total == Decimal('250.00')
    assert order.grand_total == Decimal('2550.00')
    assert order.promotion_code == 'WELCOME10'
    assert order.promotion_redemption.status == RedemptionStatus.RESERVED

    provider = get_provider('fake')
    payment = provider.initiate_payment(order=order)
    provider.process_callback(payload={'provider_reference': payment.provider_reference, 'amount': str(payment.amount), 'currency': payment.currency})
    order.promotion_redemption.refresh_from_db()
    assert order.promotion_redemption.status == RedemptionStatus.REDEEMED
    assert promotion.redemptions.filter(status=RedemptionStatus.REDEEMED).count() == 1


@pytest.mark.django_db
def test_cancelled_coupon_reservation_is_released(client, buyer, listing, address):
    from datetime import timedelta

    Promotion.objects.create(
        shop=listing.shop, name='One use', code='ONEUSE', discount_type=DiscountType.FIXED,
        value=Decimal('100.00'), usage_limit=1, per_user_limit=1,
        starts_at=timezone.now() - timedelta(minutes=1), ends_at=timezone.now() + timedelta(days=1),
    )
    request = RequestFactory().get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()
    add_to_cart(request=request, listing=listing, quantity=1)
    order = create_checkout_order(actor=buyer, cart=get_or_create_cart(request=request), shipping_address=address, coupon_code='ONEUSE')
    release_order_inventory(order=order)
    order.promotion_redemption.refresh_from_db()
    assert order.promotion_redemption.status == RedemptionStatus.RELEASED


@pytest.mark.django_db
def test_structured_variant_and_required_personalization_flow_to_order(client, buyer, seller, listing, address):
    option = add_listing_option(actor=seller, listing=listing, name='Size', values='Small, Large')
    large = option.values.get(value='Large')
    variant = add_listing_variant(
        actor=seller,
        listing=listing,
        name='Large',
        sku='BASKET-L',
        price_override=Decimal('2800.00'),
        quantity_available=2,
        option_values=[large],
    )
    field = add_personalization_field(
        actor=seller,
        listing=listing,
        label='Name to engrave',
        instructions='Up to 20 characters',
        field_type='text',
        is_required=True,
        max_length=20,
    )
    request = RequestFactory().get('/')
    request.user = buyer
    request.session = client.session
    request.session.save()

    with pytest.raises(Exception, match='required'):
        add_to_cart(request=request, listing=listing, variant=variant, quantity=1)

    item = add_to_cart(
        request=request,
        listing=listing,
        variant=variant,
        quantity=1,
        personalization_data={str(field.id): 'Amani'},
    )
    assert item.personalization_data == {'Name to engrave': 'Amani'}
    assert item.variant.option_summary == {'Size': 'Large'}

    order = create_checkout_order(
        actor=buyer,
        cart=get_or_create_cart(request=request),
        shipping_address=address,
    )
    order_item = order.items.get()
    assert order_item.unit_price == Decimal('2800.00')
    assert order_item.personalization_data == {'Name to engrave': 'Amani'}


@pytest.mark.django_db
def test_paid_digital_product_gets_private_download_grant(client, buyer, seller, shop, category):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.marketplace.listings.services import add_digital_asset

    digital = create_listing(
        actor=seller, shop=shop, category=category, title='Printable Art',
        base_price=Decimal('500.00'), product_type='digital', quantity_available=0,
    )
    asset = add_digital_asset(
        actor=seller, listing=digital, title='Printable PDF',
        file=SimpleUploadedFile('printable.pdf', b'%PDF-test-content', content_type='application/pdf'),
        version='1.0',
    )
    try:
        publish_listing(actor=seller, listing=digital)
        request = RequestFactory().get('/')
        request.user = buyer
        request.session = client.session
        request.session.save()
        add_to_cart(request=request, listing=digital, quantity=1)
        order = create_checkout_order(
            actor=buyer, cart=get_or_create_cart(request=request),
            shipping_address=None, shipping_method_code='digital', shipping_fee=Decimal(0),
        )
        payment = get_provider('fake').initiate_payment(order=order)
        get_provider('fake').process_callback(payload={
            'provider_reference': payment.provider_reference,
            'amount': str(payment.amount), 'currency': payment.currency,
        })
        order.refresh_from_db()
        grant = order.items.get().download_grant
        assert order.fulfillment_status == FulfillmentStatus.DELIVERED

        client.force_login(buyer)
        response = client.get(reverse('orders:download_asset', kwargs={'grant_id': grant.id, 'asset_id': asset.id}))
        assert response.status_code == 200
        response.close()
        other = User.objects.create_user(email='not-buyer@ziuza.co.ke', password=PASSWORD)
        client.force_login(other)
        assert client.get(reverse('orders:download_asset', kwargs={'grant_id': grant.id, 'asset_id': asset.id})).status_code == 404
    finally:
        asset.file.delete(save=False)


@pytest.mark.django_db
def test_custom_order_request_notifies_seller_and_is_owner_scoped(buyer, seller, listing):
    from apps.marketplace.messaging.models import create_custom_order_request, respond_to_custom_order

    listing.product_type = 'made_to_order'
    listing.save(update_fields=['product_type'])
    custom = create_custom_order_request(
        actor=buyer, shop=listing.shop, listing=listing,
        description='Please make this basket in a larger size with blue details.',
        budget=Decimal('4000.00'),
    )
    assert seller.notifications.filter(type='custom_order').exists()
    respond_to_custom_order(actor=seller, custom_request=custom, response='We can make this within two weeks.', status='accepted')
    custom.refresh_from_db()
    assert custom.status == 'accepted'
    assert buyer.notifications.filter(type='custom_order_response').exists()
