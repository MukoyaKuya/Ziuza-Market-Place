"""Seller dashboard views for shops."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.marketplace.listings.models import ListingStatus
from apps.marketplace.listings.selectors import seller_listings_for_shop
from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.forms import (
    ShopMarketingForm,
    ShopSectionForm,
    ShopSettingsForm,
)
from apps.marketplace.shops.marketing import delete_shop_section, save_shop_section, update_shop_marketing
from apps.marketplace.shops.models import Shop, ShopTeamRole, ShopVerificationStatus
from apps.marketplace.shops.permissions import (
    MANAGE_STOREFRONT,
    ensure_shop_owner,
    ensure_shop_permission,
)
from apps.marketplace.shops.selectors import (
    dashboard_listing_stats,
    get_shop_for_user,
    get_shop_membership,
    get_shop_section,
    shop_dashboard_reviews,
    shop_pending_team_invitations,
    shop_recent_audit_events,
    shop_team_memberships,
    shop_verification_applications,
    storefront_sections,
)
from apps.marketplace.shops.services import update_shop_settings
from apps.marketplace.shops.team_services import change_team_role, invite_team_member, revoke_team_member
from apps.marketplace.shops.trust_services import submit_verification


def _with_shop(view):
    """Require login + owned shop; otherwise send seller to onboarding."""

    @login_required
    def wrapped(request, *args, **kwargs):
        shop = get_shop_for_user(user=request.user)
        if shop is None:
            messages.info(request, 'Open a shop to access the seller dashboard.')
            return redirect('shops:onboarding')
        return view(request, shop, *args, **kwargs)

    wrapped.__name__ = view.__name__
    wrapped.__doc__ = view.__doc__
    return wrapped


@_with_shop
def dashboard_overview(request, shop):
    from apps.marketplace.analytics.selectors import shop_analytics_summary

    stats = dashboard_listing_stats(shop=shop)
    summary = shop_analytics_summary(shop=shop)
    return render(
        request,
        'shops/dashboard/overview.html',
        dashboard_context(actor=request.user,
            shop=shop,
            section='overview',
            verification_label=shop.get_verification_status_display(),
            is_verified=shop.verification_status == ShopVerificationStatus.VERIFIED,
            active_listings_count=stats['active_count'],
            draft_listings_count=stats['draft_count'],
            low_stock_count=stats['low_stock_count'],
            total_listings_count=stats['total_count'],
            paid_orders_count=summary['lifetime_order_count'],
            gross_sales=summary['lifetime_revenue'],
            units_sold=summary['lifetime_units_sold'],
            avg_rating=summary['avg_rating'],
            review_count=summary['review_count'],
            pending_fulfillment=summary['pending_fulfillment'],
            recent_orders=summary['recent_orders'],
            top_listings=summary['top_listings'][:3],
        ),
    )


@_with_shop
@require_http_methods(['GET', 'POST'])
def dashboard_shop_settings(request, shop):
    ensure_shop_owner(actor=request.user, shop=shop)
    form = ShopSettingsForm(request.POST or None, instance=shop)
    if request.method == 'POST' and form.is_valid():
        update_shop_settings(actor=request.user, shop=shop, **form.cleaned_data)
        messages.success(request, 'Shop settings saved.')
        return redirect('shops:dashboard_shop')

    return render(
        request,
        'shops/dashboard/shop_settings.html',
        dashboard_context(actor=request.user, shop=shop, section='shop', form=form),
    )


@_with_shop
@require_http_methods(['GET', 'POST'])
def storefront_marketing(request, shop):
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_STOREFRONT)
    marketing_form = ShopMarketingForm(instance=shop)
    section_form = ShopSectionForm(shop=shop)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'marketing':
            marketing_form = ShopMarketingForm(request.POST, request.FILES, instance=shop)
            if marketing_form.is_valid():
                update_shop_marketing(actor=request.user, shop=shop, **marketing_form.cleaned_data)
                messages.success(request, 'Storefront appearance and search preview saved.')
                return redirect('shops:storefront')
        elif action == 'save_section':
            section = None
            section_id = request.POST.get('section_id')
            if section_id:
                section = get_shop_section(shop=shop, section_id=section_id)
                if section is None:
                    raise Http404('Section not found.')
            section_form = ShopSectionForm(request.POST, shop=shop)
            if section_form.is_valid():
                try:
                    save_shop_section(actor=request.user, shop=shop, section=section, **section_form.cleaned_data)
                except ValidationError as exc:
                    section_form.add_error(None, exc)
                else:
                    messages.success(request, 'Shop section saved.')
                    return redirect('shops:storefront')
        elif action == 'delete_section':
            section = get_shop_section(shop=shop, section_id=request.POST.get('section_id'))
            if section is None:
                raise Http404('Section not found.')
            delete_shop_section(actor=request.user, shop=shop, section=section)
            messages.success(request, 'Shop section removed.')
            return redirect('shops:storefront')

    sections = storefront_sections(shop=shop)
    return render(request, 'shops/dashboard/storefront.html', dashboard_context(actor=request.user,
        shop=shop,
        section='storefront',
        marketing_form=marketing_form,
        section_form=section_form,
        sections=sections,
        seller_listings=seller_listings_for_shop(shop=shop).exclude(status=ListingStatus.ARCHIVED),
    ))


@_with_shop
def dashboard_reviews(request, shop):
    from apps.marketplace.shops.permissions import MANAGE_SUPPORT, user_has_shop_permission

    return render(
        request,
        'shops/dashboard/reviews.html',
        dashboard_context(
            actor=request.user,
            shop=shop,
            section='reviews',
            reviews=shop_dashboard_reviews(shop=shop),
            can_respond_to_reviews=user_has_shop_permission(
                actor=request.user, shop=shop, permission=MANAGE_SUPPORT
            ),
        ),
    )


@_with_shop
@require_http_methods(['GET', 'POST'])
def verification(request, shop):
    ensure_shop_owner(actor=request.user, shop=shop)
    if request.method == 'POST':
        try:
            submit_verification(
                actor=request.user,
                shop=shop,
                legal_name=request.POST.get('legal_name') or '',
                identity_type=request.POST.get('identity_type') or '',
                identity_last4=request.POST.get('identity_last4') or '',
                contact_phone=request.POST.get('contact_phone') or '',
                business_registration_number=request.POST.get('business_registration_number') or '',
                consent_confirmed=request.POST.get('consent_confirmed') == 'on',
            )
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(request, 'Verification application submitted for review.')
            return redirect('shops:verification')
    applications = shop_verification_applications(shop=shop)
    from apps.marketplace.shops.models import VerificationApplication
    return render(request, 'shops/dashboard/verification.html', dashboard_context(actor=request.user,
        shop=shop,
        section='verification',
        applications=applications,
        identity_types=VerificationApplication.IdentityType.choices,
    ))


@_with_shop
@require_http_methods(['GET', 'POST'])
def team_management(request, shop):
    is_owner = shop.owner_id == request.user.id
    if request.method == 'POST':
        if not is_owner:
            raise Http404('Team management not found.')
        action = request.POST.get('action')
        try:
            if action == 'invite':
                invite_team_member(
                    actor=request.user,
                    shop=shop,
                    email=request.POST.get('email') or '',
                    role=request.POST.get('role') or '',
                )
                messages.success(request, 'Team invitation sent through Ziuza notifications and email queue.')
            elif action in {'change_role', 'revoke'}:
                membership = get_shop_membership(shop=shop, membership_id=request.POST.get('membership_id'))
                if membership is None:
                    raise Http404('Team member not found.')
                if action == 'change_role':
                    change_team_role(actor=request.user, shop=shop, membership=membership, role=request.POST.get('role') or '')
                    messages.success(request, 'Team role updated.')
                else:
                    revoke_team_member(actor=request.user, shop=shop, membership=membership)
                    messages.success(request, 'Team access revoked.')
            else:
                raise ValidationError('Choose a valid team action.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        return redirect('shops:team')
    return render(request, 'shops/dashboard/team.html', dashboard_context(actor=request.user,
        shop=shop,
        section='team',
        is_team_owner=is_owner,
        memberships=shop_team_memberships(shop=shop),
        invitations=shop_pending_team_invitations(shop=shop),
        audit_events=shop_recent_audit_events(shop=shop) if is_owner else [],
        team_roles=ShopTeamRole.choices,
    ))


@_with_shop
@require_http_methods(['GET', 'POST'])
def dashboard_gifts(request, shop: Shop):
    """Seller Dashboard -> Gift Section (Zawadi) Approval Application."""
    from apps.marketplace.shops.models import ShopGiftApprovalStatus

    ctx = dashboard_context(shop=shop, section='gifts', actor=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'request_approval':
            notes = request.POST.get('notes', '').strip()
            shop.gift_approval_status = ShopGiftApprovalStatus.PENDING
            shop.gift_request_notes = notes
            shop.save(update_fields=['gift_approval_status', 'gift_request_notes', 'updated_at'])
            messages.success(
                request,
                'Your request to sell in the Zawadi Exclusive Gift Section has been submitted to Admin for review.',
            )
            return redirect('shops:dashboard_gifts')

    ctx.update({
        'shop': shop,
        'gift_approval_status': shop.gift_approval_status,
        'page_title': 'Gift Section (Zawadi) | Seller Dashboard',
    })
    return render(request, 'shops/dashboard_gifts.html', ctx)
