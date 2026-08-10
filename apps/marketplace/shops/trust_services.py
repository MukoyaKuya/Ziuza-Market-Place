from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.notifications.services import notify
from apps.marketplace.shops.models import (
    MarketplaceReport, ModerationAction, ReportReason, ReportStatus, Shop,
    ShopVerificationStatus, VerificationApplication, VerificationApplicationStatus,
)
from apps.marketplace.shops.permissions import ensure_shop_owner


@transaction.atomic
def submit_verification(*, actor, shop: Shop, legal_name: str, identity_type: str, identity_last4: str, contact_phone: str, business_registration_number: str = '', consent_confirmed: bool = False):
    ensure_shop_owner(actor=actor, shop=shop)
    if VerificationApplication.objects.filter(shop=shop, status=VerificationApplicationStatus.PENDING).exists():
        raise ValidationError('A verification application is already under review.')
    if not legal_name.strip() or not contact_phone.strip():
        raise ValidationError('Legal name and contact phone are required.')
    last4 = ''.join(character for character in identity_last4 if character.isalnum())[-4:]
    if len(last4) != 4:
        raise ValidationError('Provide only the final four characters of the identity document number.')
    if identity_type not in VerificationApplication.IdentityType.values:
        raise ValidationError('Choose a valid identity type.')
    if not consent_confirmed:
        raise ValidationError('Consent is required to submit verification information.')
    application = VerificationApplication.objects.create(
        shop=shop,
        legal_name=legal_name.strip(),
        identity_type=identity_type,
        identity_last4=last4,
        contact_phone=contact_phone.strip(),
        business_registration_number=business_registration_number.strip(),
        consent_confirmed=True,
    )
    shop.verification_status = ShopVerificationStatus.PENDING
    shop.save(update_fields=['verification_status', 'updated_at'])
    return application


@transaction.atomic
def review_verification(*, actor, application: VerificationApplication, approved: bool, notes: str = ''):
    if not actor.is_staff:
        raise PermissionDenied
    notes = notes.strip()
    if not approved and not notes:
        raise ValidationError('Explain what the seller needs to correct before rejecting verification.')
    application = VerificationApplication.objects.select_for_update().select_related('shop__owner').get(pk=application.pk)
    if application.status != VerificationApplicationStatus.PENDING:
        raise ValidationError('This verification application has already been reviewed.')
    application.status = VerificationApplicationStatus.APPROVED if approved else VerificationApplicationStatus.REJECTED
    application.reviewer_notes = notes
    application.reviewed_by = actor
    application.reviewed_at = timezone.now()
    application.save()
    application.shop.verification_status = ShopVerificationStatus.VERIFIED if approved else ShopVerificationStatus.REJECTED
    application.shop.save(update_fields=['verification_status', 'updated_at'])
    ModerationAction.objects.create(
        actor=actor,
        action=ModerationAction.Action.VERIFY_SHOP if approved else ModerationAction.Action.REJECT_VERIFICATION,
        shop=application.shop,
        notes=notes,
    )
    notify(
        recipient=application.shop.owner,
        type='verification_reviewed',
        title='Shop verification approved' if approved else 'Shop verification needs attention',
        body=notes,
        target_url='/seller/verification/',
    )
    return application


def create_report(*, actor, reason: str, details: str, shop: Shop | None = None, listing: Listing | None = None):
    if not actor.is_authenticated:
        raise PermissionDenied
    if bool(shop) == bool(listing):
        raise ValidationError('Choose exactly one report target.')
    if reason not in ReportReason.values:
        raise ValidationError('Choose a valid report reason.')
    if (shop and shop.owner_id == actor.id) or (listing and listing.shop.owner_id == actor.id):
        raise ValidationError('You cannot report your own shop or listing.')
    details = details.strip()
    if len(details) < 20:
        raise ValidationError('Provide at least 20 characters of detail.')
    duplicate_target = {'shop': shop} if shop else {'listing': listing}
    if MarketplaceReport.objects.filter(reporter=actor, status__in=[ReportStatus.OPEN, ReportStatus.REVIEWING], **duplicate_target).exists():
        raise ValidationError('You already have an active report for this item.')
    return MarketplaceReport.objects.create(reporter=actor, shop=shop, listing=listing, reason=reason, details=details)


@transaction.atomic
def moderate_report(*, actor, report: MarketplaceReport, action: str, notes: str = ''):
    if not actor.is_staff:
        raise PermissionDenied
    report = MarketplaceReport.objects.select_for_update().select_related('shop', 'listing__shop').get(pk=report.pk)
    if report.status not in {ReportStatus.OPEN, ReportStatus.REVIEWING}:
        raise ValidationError('This report has already been resolved.')
    target_shop = report.shop or report.listing.shop
    if action == ModerationAction.Action.SUSPEND_SHOP:
        target_shop.verification_status = ShopVerificationStatus.SUSPENDED
        target_shop.save(update_fields=['verification_status', 'updated_at'])
    elif action == ModerationAction.Action.HIDE_LISTING and report.listing:
        report.listing.status = ListingStatus.PAUSED
        report.listing.save(update_fields=['status', 'updated_at'])
    elif action != ModerationAction.Action.DISMISS_REPORT:
        raise ValidationError('Invalid moderation action for this report.')
    report.status = ReportStatus.DISMISSED if action == ModerationAction.Action.DISMISS_REPORT else ReportStatus.ACTIONED
    report.moderator_notes = notes.strip()
    report.save(update_fields=['status', 'moderator_notes', 'updated_at'])
    ModerationAction.objects.create(actor=actor, action=action, shop=target_shop, listing=report.listing, report=report, notes=notes)
    notify(recipient=target_shop.owner, type='moderation', title='Marketplace moderation update', body=notes, target_url='/seller/')
    return report
