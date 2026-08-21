import uuid

from django.conf import settings
from django.db import models


class VerificationApplicationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class VerificationApplication(models.Model):
    class IdentityType(models.TextChoices):
        NATIONAL_ID = 'national_id', 'Kenyan national ID'
        PASSPORT = 'passport', 'Passport'
        BUSINESS = 'business', 'Business registration'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='verification_applications')
    legal_name = models.CharField(max_length=160)
    identity_type = models.CharField(max_length=24, choices=IdentityType.choices)
    identity_last4 = models.CharField(max_length=4)
    business_registration_number = models.CharField(max_length=80, blank=True)
    contact_phone = models.CharField(max_length=20)
    consent_confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=VerificationApplicationStatus.choices, default=VerificationApplicationStatus.PENDING, db_index=True)
    reviewer_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reviewed_verification_applications',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']


class ReportReason(models.TextChoices):
    PROHIBITED = 'prohibited', 'Prohibited or unsafe item'
    COUNTERFEIT = 'counterfeit', 'Counterfeit or intellectual-property concern'
    MISLEADING = 'misleading', 'Misleading listing or shop'
    FRAUD = 'fraud', 'Suspected fraud or scam'
    HARASSMENT = 'harassment', 'Harassment or abusive conduct'
    OTHER = 'other', 'Other concern'


class ReportStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    REVIEWING = 'reviewing', 'Under review'
    ACTIONED = 'actioned', 'Action taken'
    DISMISSED = 'dismissed', 'Dismissed'


class MarketplaceReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='marketplace_reports')
    shop = models.ForeignKey('shops.Shop', null=True, blank=True, on_delete=models.CASCADE, related_name='reports')
    listing = models.ForeignKey('listings.Listing', null=True, blank=True, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=24, choices=ReportReason.choices)
    details = models.TextField()
    status = models.CharField(max_length=20, choices=ReportStatus.choices, default=ReportStatus.OPEN, db_index=True)
    moderator_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(shop__isnull=False, listing__isnull=True) | models.Q(shop__isnull=True, listing__isnull=False)),
                name='report_exactly_one_target',
            )
        ]


class ModerationAction(models.Model):
    class Action(models.TextChoices):
        VERIFY_SHOP = 'verify_shop', 'Verify shop'
        REJECT_VERIFICATION = 'reject_verification', 'Reject verification'
        SUSPEND_SHOP = 'suspend_shop', 'Suspend shop'
        RESTORE_SHOP = 'restore_shop', 'Restore shop'
        HIDE_LISTING = 'hide_listing', 'Hide listing'
        DISMISS_REPORT = 'dismiss_report', 'Dismiss report'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='moderation_actions')
    action = models.CharField(max_length=32, choices=Action.choices)
    shop = models.ForeignKey('shops.Shop', null=True, blank=True, on_delete=models.SET_NULL, related_name='moderation_actions')
    listing = models.ForeignKey('listings.Listing', null=True, blank=True, on_delete=models.SET_NULL, related_name='moderation_actions')
    report = models.ForeignKey(MarketplaceReport, null=True, blank=True, on_delete=models.SET_NULL, related_name='actions')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
