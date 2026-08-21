import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ReviewModerationStatus(models.TextChoices):
    PUBLISHED = 'published', 'Published'
    REPORTED = 'reported', 'Reported'
    HIDDEN = 'hidden', 'Hidden'


class ReviewReportReason(models.TextChoices):
    SPAM = 'spam', 'Spam or advertising'
    ABUSE = 'abuse', 'Abusive or hateful content'
    PRIVACY = 'privacy', 'Personal or private information'
    IRRELEVANT = 'irrelevant', 'Not about this purchase'
    MANIPULATION = 'manipulation', 'Suspicious or manipulated review'
    OTHER = 'other', 'Other concern'


class ReviewReportStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    DISMISSED = 'dismissed', 'Dismissed'
    ACTIONED = 'actioned', 'Actioned'


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='reviews')
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='reviews')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    order_item = models.OneToOneField('orders.OrderItem', on_delete=models.CASCADE, related_name='review')
    rating = models.PositiveSmallIntegerField()
    quality_rating = models.PositiveSmallIntegerField(default=5)
    shipping_rating = models.PositiveSmallIntegerField(default=5)
    service_rating = models.PositiveSmallIntegerField(default=5)
    title = models.CharField(max_length=160, blank=True)
    body = models.TextField(blank=True)
    is_visible = models.BooleanField(default=True)
    is_verified_purchase = models.BooleanField(default=True)
    moderation_status = models.CharField(max_length=20, choices=ReviewModerationStatus.choices, default=ReviewModerationStatus.PUBLISHED, db_index=True)
    seller_response = models.TextField(blank=True)
    seller_responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='review_responses')
    seller_responded_at = models.DateTimeField(null=True, blank=True)
    helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def edit_deadline(self):
        return self.created_at + timedelta(days=30)

    @property
    def can_edit(self):
        return timezone.now() <= self.edit_deadline


class ReviewMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='media')
    image = models.ImageField(upload_to='reviews/%Y/%m/%d')
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=80)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class ReviewHelpfulVote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_helpful_votes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['review', 'user'], name='uniq_review_helpful_user')]


class ReviewReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_reports')
    reason = models.CharField(max_length=24, choices=ReviewReportReason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=ReviewReportStatus.choices, default=ReviewReportStatus.OPEN, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='moderated_review_reports')
    moderator_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['review', 'reporter'], name='uniq_review_reporter')]


class ReviewReminder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.OneToOneField('orders.OrderItem', on_delete=models.CASCADE, related_name='review_reminder')
    sent_at = models.DateTimeField(auto_now_add=True)


def create_review(**kwargs):
    """Backward-compatible public entrypoint; implementation lives in review services."""
    from apps.marketplace.reviews.services import create_review as create
    return create(**kwargs)
