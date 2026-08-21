import uuid
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.services import create_listing, publish_listing
from apps.marketplace.orders.models import FulfillmentStatus, Order, OrderItem, PaymentStatus, SellerOrder
from apps.marketplace.reviews.models import (
    Review,
    ReviewMedia,
    ReviewModerationStatus,
    ReviewReportReason,
    ReviewReportStatus,
)
from apps.marketplace.reviews.services import (
    create_review,
    moderate_review_report,
    process_review_reminders,
    report_review,
    respond_to_review,
    toggle_helpful_vote,
    update_review,
)
from apps.marketplace.shops.models import ShopMembership, ShopTeamRole
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


def png_upload(name='review.png'):
    stream = BytesIO()
    Image.new('RGB', (8, 8), color=(20, 120, 70)).save(stream, format='PNG')
    return SimpleUploadedFile(name, stream.getvalue(), content_type='image/png')


@pytest.fixture
def review_setup(db):
    seller = User.objects.create_user(email='review-seller@ziuza.co.ke', password=PASSWORD, display_name='Seller')
    buyer = User.objects.create_user(email='review-buyer@ziuza.co.ke', password=PASSWORD, display_name='Buyer')
    support = User.objects.create_user(email='review-support@ziuza.co.ke', password=PASSWORD, display_name='Support')
    outsider = User.objects.create_user(email='review-outsider@ziuza.co.ke', password=PASSWORD, display_name='Outsider')
    category = Category.objects.create(name='Review Craft', slug='review-craft', is_visible=True)
    shop = create_shop(actor=seller, name='Review Studio', county='Nairobi')
    ShopMembership.objects.create(shop=shop, user=support, role=ShopTeamRole.SUPPORT, invited_by=seller)
    listing = create_listing(
        actor=seller, shop=shop, category=category, title='Reviewed Basket',
        base_price=Decimal('1500.00'), quantity_available=4,
    )
    publish_listing(actor=seller, listing=listing)
    order = Order.objects.create(
        public_number=f'REVIEW-{uuid.uuid4().hex[:8]}', buyer=buyer,
        payment_status=PaymentStatus.PAID, fulfillment_status=FulfillmentStatus.DELIVERED,
        subtotal=Decimal('1500.00'), grand_total=Decimal('1500.00'),
    )
    seller_order = SellerOrder.objects.create(
        order=order, shop=shop, fulfillment_status=FulfillmentStatus.DELIVERED,
        subtotal=Decimal('1500.00'),
    )
    item = OrderItem.objects.create(
        order=order, seller_order=seller_order, shop=shop, listing_id=listing.id,
        title_snapshot=listing.title, unit_price=listing.base_price, quantity=1,
        line_total=listing.base_price,
    )
    yield seller, buyer, support, outsider, shop, listing, order, seller_order, item
    for media in ReviewMedia.objects.all():
        media.image.delete(save=False)


def make_review(buyer, item, **overrides):
    fields = {
        'actor': buyer, 'order_item': item, 'rating': 5,
        'quality_rating': 5, 'shipping_rating': 4, 'service_rating': 5,
        'title': 'Beautiful work', 'body': 'The item matched the listing and arrived safely.',
    }
    fields.update(overrides)
    return create_review(**fields)


@pytest.mark.django_db
def test_verified_review_requires_confirmed_delivery_and_blocks_shop_team(review_setup):
    seller, buyer, _, _, shop, _, _, seller_order, item = review_setup
    seller_order.fulfillment_status = FulfillmentStatus.SHIPPED
    seller_order.save(update_fields=['fulfillment_status'])
    with pytest.raises(ValidationError, match='confirmed'):
        make_review(buyer, item)
    seller_order.fulfillment_status = FulfillmentStatus.DELIVERED
    seller_order.save(update_fields=['fulfillment_status'])
    ShopMembership.objects.create(shop=shop, user=buyer, role=ShopTeamRole.SUPPORT, invited_by=seller)
    with pytest.raises(ValidationError, match='team members'):
        make_review(buyer, item)


@pytest.mark.django_db
def test_review_records_breakdown_photo_verification_and_shop_rating(review_setup):
    _, buyer, _, _, shop, _, _, _, item = review_setup
    review = make_review(buyer, item, rating=4, quality_rating=5, shipping_rating=3, service_rating=4, photos=[png_upload()])
    shop.refresh_from_db()
    assert review.is_verified_purchase
    assert (review.quality_rating, review.shipping_rating, review.service_rating) == (5, 3, 4)
    assert review.media.count() == 1
    assert shop.rating_count == 1
    assert shop.rating_average == Decimal('4.00')


@pytest.mark.django_db
def test_photo_content_spoofing_and_limit_are_rejected(review_setup):
    _, buyer, _, _, _, _, _, _, item = review_setup
    spoofed = SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')
    with pytest.raises(ValidationError, match='contents'):
        make_review(buyer, item, photos=[spoofed])
    with pytest.raises(ValidationError, match='up to 4'):
        make_review(buyer, item, photos=[png_upload(f'{i}.png') for i in range(5)])


@pytest.mark.django_db
def test_review_edit_window_and_rating_recalculation(review_setup):
    _, buyer, _, _, shop, _, _, _, item = review_setup
    review = make_review(buyer, item, rating=5)
    update_review(
        actor=buyer, review=review, rating=2, quality_rating=2, shipping_rating=2,
        service_rating=3, title='Updated', body='My updated experience.', photos=[],
    )
    shop.refresh_from_db()
    assert shop.rating_average == Decimal('2.00')
    Review.objects.filter(pk=review.pk).update(created_at=timezone.now() - timedelta(days=31))
    review.refresh_from_db()
    with pytest.raises(ValidationError, match='30 days'):
        update_review(actor=buyer, review=review, rating=3, title='', body='', photos=[])


@pytest.mark.django_db
def test_support_role_can_respond_and_buyer_is_notified(review_setup):
    _, buyer, support, outsider, _, _, _, _, item = review_setup
    review = make_review(buyer, item)
    with pytest.raises(PermissionDenied):
        respond_to_review(actor=outsider, review=review, response='Unauthorized response')
    respond_to_review(actor=support, review=review, response='Thank you; we appreciate your detailed feedback.')
    review.refresh_from_db()
    assert review.seller_responded_by == support
    assert buyer.notifications.filter(type='review_response').exists()


@pytest.mark.django_db
def test_helpful_votes_are_unique_toggleable_and_not_self_votes(review_setup):
    _, buyer, _, outsider, _, _, _, _, item = review_setup
    review = make_review(buyer, item)
    with pytest.raises(ValidationError, match='own review'):
        toggle_helpful_vote(actor=buyer, review=review)
    assert toggle_helpful_vote(actor=outsider, review=review)
    review.refresh_from_db()
    assert review.helpful_count == 1
    assert not toggle_helpful_vote(actor=outsider, review=review)
    review.refresh_from_db()
    assert review.helpful_count == 0


@pytest.mark.django_db
def test_review_report_moderation_hides_review_and_recalculates_reputation(review_setup):
    _, buyer, _, outsider, shop, _, _, _, item = review_setup
    review = make_review(buyer, item, rating=1)
    report = report_review(actor=outsider, review=review, reason=ReviewReportReason.ABUSE, details='Contains inappropriate material.')
    review.refresh_from_db()
    assert review.moderation_status == ReviewModerationStatus.REPORTED
    moderator = User.objects.create_superuser(email='review-mod@ziuza.co.ke', password=PASSWORD)
    moderate_review_report(actor=moderator, report=report, hide=True, notes='Review violates marketplace policy.')
    report.refresh_from_db()
    review.refresh_from_db()
    shop.refresh_from_db()
    assert report.status == ReviewReportStatus.ACTIONED
    assert not review.is_visible
    assert review.moderation_status == ReviewModerationStatus.HIDDEN
    assert shop.rating_count == 0


@pytest.mark.django_db
def test_review_reminder_is_sent_once_after_delivery_delay(review_setup):
    _, buyer, _, _, _, _, _, seller_order, item = review_setup
    SellerOrder.objects.filter(pk=seller_order.pk).update(updated_at=timezone.now() - timedelta(days=4))
    assert process_review_reminders() == 1
    assert buyer.notifications.filter(type='review_reminder', target_url__contains=str(item.id)).exists()
    assert process_review_reminders() == 0


@pytest.mark.django_db
def test_review_pages_create_display_edit_and_seller_response(client, review_setup):
    seller, buyer, _, _, shop, listing, _, _, item = review_setup
    client.force_login(buyer)
    response = client.post(reverse('reviews:create', kwargs={'order_item_id': item.id}), {
        'rating': '5', 'quality_rating': '5', 'shipping_rating': '4', 'service_rating': '5',
        'title': 'Verified and lovely', 'body': 'A detailed review from a confirmed buyer.',
        'photos': png_upload('page.png'),
    })
    assert response.status_code == 302
    review = Review.objects.get(order_item=item)
    listing_page = client.get(reverse('listings:detail', kwargs={'slug': listing.slug}))
    assert b'Verified purchase reviews' in listing_page.content
    assert b'Verified and lovely' in listing_page.content
    client.force_login(seller)
    response = client.post(reverse('reviews:seller_response', kwargs={'review_id': review.id}), {'response': 'Thank you for supporting our studio.'})
    assert response.status_code == 302
    shop_page = client.get(reverse('shops:public_shop', kwargs={'slug': shop.slug}))
    assert b'Thank you for supporting our studio.' in shop_page.content
