from datetime import timedelta
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone

from apps.marketplace.notifications.services import notify
from apps.marketplace.orders.models import FulfillmentStatus, OrderItem, PaymentStatus
from apps.marketplace.reviews.models import (
    Review, ReviewHelpfulVote, ReviewMedia, ReviewModerationStatus, ReviewReminder,
    ReviewReport, ReviewReportReason, ReviewReportStatus,
)
from apps.marketplace.shops.permissions import MANAGE_SUPPORT, ensure_shop_permission, user_is_shop_staff


EDIT_WINDOW_DAYS = 30
MAX_REVIEW_MEDIA = 4
MAX_IMAGE_SIZE = 8 * 1024 * 1024
IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


def _rating(value, label):
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'{label} must be from 1 to 5.') from exc
    if value < 1 or value > 5:
        raise ValidationError(f'{label} must be from 1 to 5.')
    return value


def _validate_image(upload):
    if upload.size > MAX_IMAGE_SIZE:
        raise ValidationError('Review photos must be 8 MB or smaller.')
    content_type = (getattr(upload, 'content_type', '') or '').lower()
    if content_type not in IMAGE_TYPES:
        raise ValidationError('Upload review photos as JPG, PNG, or WebP.')
    header = upload.read(12)
    upload.seek(0)
    signature_ok = (
        content_type == 'image/jpeg' and header.startswith(b'\xff\xd8\xff')
        or content_type == 'image/png' and header.startswith(b'\x89PNG\r\n\x1a\n')
        or content_type == 'image/webp' and header.startswith(b'RIFF') and header[8:12] == b'WEBP'
    )
    if not signature_ok:
        raise ValidationError('Review photo contents do not match the selected file type.')
    try:
        from PIL import Image
        image = Image.open(upload)
        image.verify()
        upload.seek(0)
    except Exception as exc:
        upload.seek(0)
        raise ValidationError('The review photo is damaged or invalid.') from exc
    return content_type


def recalculate_shop_rating(shop):
    stats = Review.objects.filter(
        shop=shop, is_visible=True, moderation_status=ReviewModerationStatus.PUBLISHED,
    ).aggregate(count=Count('id'), average=Avg('rating'))
    shop.rating_count = stats['count'] or 0
    shop.rating_average = stats['average'] or 0
    shop.save(update_fields=['rating_count', 'rating_average', 'updated_at'])
def _add_media(*, review, uploads):
    uploads = list(uploads or [])
    remaining = MAX_REVIEW_MEDIA - review.media.count()
    if len(uploads) > remaining:
        raise ValidationError(f'A review can include up to {MAX_REVIEW_MEDIA} photos.')
    validated = [(upload, _validate_image(upload)) for upload in uploads]
    return [ReviewMedia.objects.create(
        review=review, image=upload, original_name=Path(upload.name).name[:255],
        content_type=content_type, size=upload.size,
    ) for upload, content_type in validated]


@transaction.atomic
def create_review(*, actor, order_item, rating, title='', body='', quality_rating=None,
                  shipping_rating=None, service_rating=None, photos=None):
    if order_item.order.buyer_id != actor.id:
        raise ValidationError('You can only review your own purchases.')
    if order_item.order.payment_status != PaymentStatus.PAID:
        raise ValidationError('Order must be paid before reviewing.')
    if order_item.seller_order.fulfillment_status != FulfillmentStatus.DELIVERED:
        raise ValidationError('Delivery must be confirmed before reviewing.')
    if user_is_shop_staff(actor=actor, shop=order_item.seller_order.shop):
        raise ValidationError('Shop owners and team members cannot review their own shop.')
    if Review.objects.filter(order_item=order_item).exists():
        raise ValidationError('This purchased item has already been reviewed.')
    overall = _rating(rating, 'Overall rating')
    from apps.marketplace.listings.models import Listing
    listing = Listing.objects.filter(id=order_item.listing_id).first() if order_item.listing_id else None
    if listing is None:
        raise ValidationError('Listing unavailable for review.')
    review = Review.objects.create(
        listing=listing, shop=order_item.seller_order.shop, buyer=actor, order_item=order_item,
        rating=overall, quality_rating=_rating(quality_rating or overall, 'Product quality'),
        shipping_rating=_rating(shipping_rating or overall, 'Delivery'),
        service_rating=_rating(service_rating or overall, 'Seller service'),
        title=title.strip()[:160], body=body.strip(), is_verified_purchase=True,
    )
    _add_media(review=review, uploads=photos)
    recalculate_shop_rating(review.shop)
    notify(
        recipient=review.shop.owner, type='review_received',
        title=f'New verified review for {listing.title}', body=f'{overall}/5 stars',
        target_url='/seller/reviews/',
    )
    return review


@transaction.atomic
def update_review(*, actor, review, rating, title='', body='', quality_rating=None,
                  shipping_rating=None, service_rating=None, photos=None):
    if review.buyer_id != actor.id:
        raise PermissionDenied
    if not review.can_edit:
        raise ValidationError(f'Reviews can only be edited within {EDIT_WINDOW_DAYS} days.')
    overall = _rating(rating, 'Overall rating')
    review.rating = overall
    review.quality_rating = _rating(quality_rating or overall, 'Product quality')
    review.shipping_rating = _rating(shipping_rating or overall, 'Delivery')
    review.service_rating = _rating(service_rating or overall, 'Seller service')
    review.title = title.strip()[:160]
    review.body = body.strip()
    review.edited_at = timezone.now()
    review.save(update_fields=['rating', 'quality_rating', 'shipping_rating', 'service_rating', 'title', 'body', 'edited_at'])
    _add_media(review=review, uploads=photos)
    recalculate_shop_rating(review.shop)
    return review


@transaction.atomic
def delete_review_media(*, actor, media):
    if media.review.buyer_id != actor.id:
        raise PermissionDenied
    if not media.review.can_edit:
        raise ValidationError('The review editing window has closed.')
    media.image.delete(save=False)
    media.delete()


@transaction.atomic
def respond_to_review(*, actor, review, response):
    ensure_shop_permission(actor=actor, shop=review.shop, permission=MANAGE_SUPPORT)
    if not review.is_visible or review.moderation_status == ReviewModerationStatus.HIDDEN:
        raise ValidationError('A hidden review cannot receive a public response.')
    response = response.strip()
    if len(response) < 3 or len(response) > 1000:
        raise ValidationError('Seller response must be between 3 and 1,000 characters.')
    review.seller_response = response
    review.seller_responded_by = actor
    review.seller_responded_at = timezone.now()
    review.save(update_fields=['seller_response', 'seller_responded_by', 'seller_responded_at'])
    notify(recipient=review.buyer, type='review_response', title=f'{review.shop.name} responded to your review', target_url=f'/listing/{review.listing.slug}/')
    return review


@transaction.atomic
def toggle_helpful_vote(*, actor, review):
    if review.buyer_id == actor.id:
        raise ValidationError('You cannot vote on your own review.')
    vote, created = ReviewHelpfulVote.objects.get_or_create(review=review, user=actor)
    if not created:
        vote.delete()
    review.helpful_count = review.helpful_votes.count()
    review.save(update_fields=['helpful_count'])
    return created


@transaction.atomic
def report_review(*, actor, review, reason, details=''):
    if review.buyer_id == actor.id:
        raise ValidationError('You cannot report your own review.')
    if reason not in ReviewReportReason.values:
        raise ValidationError('Choose a valid report reason.')
    if ReviewReport.objects.filter(review=review, reporter=actor).exists():
        raise ValidationError('You already reported this review.')
    report = ReviewReport.objects.create(review=review, reporter=actor, reason=reason, details=details.strip()[:2000])
    if review.moderation_status == ReviewModerationStatus.PUBLISHED:
        review.moderation_status = ReviewModerationStatus.REPORTED
        review.save(update_fields=['moderation_status'])
    return report


@transaction.atomic
def moderate_review_report(*, actor, report, hide, notes=''):
    if not actor.is_staff:
        raise PermissionDenied
    if report.status != ReviewReportStatus.OPEN:
        raise ValidationError('This report has already been reviewed.')
    now = timezone.now()
    report.status = ReviewReportStatus.ACTIONED if hide else ReviewReportStatus.DISMISSED
    report.reviewed_by = actor
    report.reviewed_at = now
    report.moderator_notes = notes.strip()
    report.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'moderator_notes'])
    review = report.review
    if hide:
        review.is_visible = False
        review.moderation_status = ReviewModerationStatus.HIDDEN
    elif not review.reports.filter(status=ReviewReportStatus.OPEN).exclude(id=report.id).exists():
        review.is_visible = True
        review.moderation_status = ReviewModerationStatus.PUBLISHED
    review.save(update_fields=['is_visible', 'moderation_status'])
    recalculate_shop_rating(review.shop)
    notify(recipient=review.buyer, type='review_moderated', title='Ziuza reviewed a report about your review', target_url=f'/listing/{review.listing.slug}/')
    return report


def process_review_reminders(*, limit=500):
    cutoff = timezone.now() - timedelta(days=3)
    item_ids = list(OrderItem.objects.filter(
        order__payment_status=PaymentStatus.PAID,
        seller_order__fulfillment_status=FulfillmentStatus.DELIVERED,
        seller_order__updated_at__lte=cutoff,
        review__isnull=True, review_reminder__isnull=True,
    ).values_list('id', flat=True)[:limit])
    sent = 0
    for item_id in item_ids:
        with transaction.atomic():
            item = OrderItem.objects.select_for_update().select_related('order__buyer').get(id=item_id)
            if Review.objects.filter(order_item=item).exists() or ReviewReminder.objects.filter(order_item=item).exists():
                continue
            ReviewReminder.objects.create(order_item=item)
            notify(
                recipient=item.order.buyer, type='review_reminder',
                title=f'How was {item.title_snapshot}?',
                body='Share a verified review to help other buyers and the maker.',
                target_url=f'/account/orders/items/{item.id}/review/',
            )
            sent += 1
    return sent
