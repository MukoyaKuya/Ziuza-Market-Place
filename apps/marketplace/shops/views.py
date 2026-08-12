from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.marketplace.listings.models import ListingStatus
from apps.marketplace.listings.selectors import public_listings_for_shop, seller_listings_for_shop
from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.forms import CreateShopForm, ShopMarketingForm, ShopSectionForm, ShopSettingsForm
from apps.marketplace.shops.models import Shop, ShopSection, ShopVerificationStatus
from apps.marketplace.shops.marketing import delete_shop_section, save_shop_section, update_shop_marketing
from apps.marketplace.shops.selectors import get_public_shop_by_slug, get_shop_for_owner, get_shop_for_user
from apps.marketplace.shops.services import create_shop, update_shop_settings
from apps.marketplace.shops.models import ReportReason
from apps.marketplace.shops.models import ShopInvitation, ShopMembership, ShopTeamRole
from apps.marketplace.shops.permissions import MANAGE_STOREFRONT, ensure_shop_owner, ensure_shop_permission
from apps.marketplace.shops.team_services import (
    accept_team_invitation, change_team_role, invitation_for_token, invite_team_member, revoke_team_member,
)
from apps.marketplace.shops.trust_services import create_report, submit_verification


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


@login_required
def sell_entry(request):
    """/sell/ — dashboard if shop exists, else onboarding."""
    if get_shop_for_user(user=request.user) is not None:
        return redirect('shops:dashboard')
    return redirect('shops:onboarding')


@login_required
@require_http_methods(['GET', 'POST'])
def shop_onboarding(request):
    if get_shop_for_user(user=request.user) is not None:
        return redirect('shops:dashboard')

    form = CreateShopForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            shop = create_shop(
                actor=request.user,
                name=form.cleaned_data['name'],
                description=form.cleaned_data.get('description') or '',
                county=form.cleaned_data['county'],
                location_text=form.cleaned_data.get('location_text') or '',
            )
        except ValidationError as exc:
            if hasattr(exc, 'message_dict'):
                for field, errors in exc.message_dict.items():
                    for error in errors:
                        form.add_error(field if field in form.fields else None, error)
            else:
                form.add_error(None, exc)
        else:
            messages.success(request, f'“{shop.name}” is ready. Welcome to your seller dashboard.')
            return redirect('shops:dashboard')

    return render(
        request,
        'shops/onboarding.html',
        {'form': form, 'page_title': 'Open your shop'},
    )


@_with_shop
def dashboard_overview(request, shop):
    from apps.marketplace.analytics.selectors import shop_analytics_summary

    listings = list(seller_listings_for_shop(shop=shop)[:50])
    active_count = sum(1 for item in listings if item.status == ListingStatus.ACTIVE)
    draft_count = sum(1 for item in listings if item.status == ListingStatus.DRAFT)
    low_stock = 0
    for item in listings:
        base = item.base_inventory[0] if getattr(item, 'base_inventory', None) else None
        if base and base.available_to_sell <= base.low_stock_threshold:
            low_stock += 1

    summary = shop_analytics_summary(shop=shop)
    return render(
        request,
        'shops/dashboard/overview.html',
        dashboard_context(actor=request.user,
            shop=shop,
            section='overview',
            verification_label=shop.get_verification_status_display(),
            is_verified=shop.verification_status == ShopVerificationStatus.VERIFIED,
            active_listings_count=active_count,
            draft_listings_count=draft_count,
            low_stock_count=low_stock,
            total_listings_count=len(listings),
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
                section = ShopSection.objects.filter(id=section_id, shop=shop).first()
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
            section = ShopSection.objects.filter(id=request.POST.get('section_id'), shop=shop).first()
            if section is None:
                raise Http404('Section not found.')
            delete_shop_section(actor=request.user, shop=shop, section=section)
            messages.success(request, 'Shop section removed.')
            return redirect('shops:storefront')

    sections = shop.sections.prefetch_related('listings').all()
    return render(request, 'shops/dashboard/storefront.html', dashboard_context(actor=request.user,
        shop=shop,
        section='storefront',
        marketing_form=marketing_form,
        section_form=section_form,
        sections=sections,
        seller_listings=seller_listings_for_shop(shop=shop).exclude(status=ListingStatus.ARCHIVED),
    ))


def _placeholder(request, shop, *, section: str, title: str, message: str):
    return render(
        request,
        'shops/dashboard/placeholder.html',
        dashboard_context(actor=request.user,
            shop=shop,
            section=section,
            placeholder_title=title,
            placeholder_message=message,
        ),
    )


@_with_shop
def dashboard_reviews(request, shop):
    from apps.marketplace.reviews.models import Review
    from apps.marketplace.shops.permissions import MANAGE_SUPPORT, user_has_shop_permission

    reviews = list(
        Review.objects.filter(shop=shop)
        .select_related('buyer', 'listing', 'seller_responded_by')
        .prefetch_related('media')[:50]
    )
    return render(
        request,
        'shops/dashboard/reviews.html',
        dashboard_context(
            actor=request.user,
            shop=shop,
            section='reviews',
            reviews=reviews,
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
    applications = shop.verification_applications.select_related('reviewed_by')[:10]
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
                membership = ShopMembership.objects.filter(id=request.POST.get('membership_id'), shop=shop).select_related('user').first()
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
        memberships=shop.memberships.select_related('user', 'invited_by'),
        invitations=shop.team_invitations.filter(accepted_at__isnull=True, revoked_at__isnull=True).select_related('invited_by')[:20],
        audit_events=shop.audit_events.select_related('actor')[:50] if is_owner else [],
        team_roles=ShopTeamRole.choices,
    ))


@login_required
@require_http_methods(['GET', 'POST'])
def accept_team(request, token):
    try:
        invitation = invitation_for_token(actor=request.user, token=token)
        if request.method == 'POST':
            accept_team_invitation(actor=request.user, token=token)
            messages.success(request, f'You joined {invitation.shop.name}.')
            return redirect('shops:dashboard')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('accounts:account_home')
    return render(request, 'shops/team_accept.html', {
        'invitation': invitation,
        'token': token,
        'page_title': f'Join {invitation.shop.name}',
    })


@login_required
@require_http_methods(['POST'])
def report_shop(request, slug):
    try:
        shop = Shop.objects.get(slug=slug)
        create_report(actor=request.user, shop=shop, reason=request.POST.get('reason') or '', details=request.POST.get('details') or '')
        messages.success(request, 'Report submitted. Ziuza will review it.')
    except Shop.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('shops:public_shop', slug=slug)


def public_shop(request, slug: str):
    try:
        shop = get_public_shop_by_slug(slug=slug)
    except Shop.DoesNotExist as exc:
        raise Http404('Shop not found.') from exc

    if shop.verification_status == ShopVerificationStatus.SUSPENDED:
        raise Http404('Shop not found.')

    sections = shop.sections.filter(is_visible=True)
    selected_section = None
    if request.GET.get('section'):
        selected_section = sections.filter(slug=request.GET['section']).first()
        if selected_section is None:
            raise Http404('Shop section not found.')
    shop_query = (request.GET.get('q') or '').strip()[:100]
    shop_sort = request.GET.get('sort') or 'newest'
    if shop_sort not in {'newest', 'price_asc', 'price_desc', 'name'}:
        shop_sort = 'newest'
    try:
        shop_limit = min(48, max(8, int(request.GET.get('limit') or 8)))
    except (TypeError, ValueError):
        shop_limit = 8
    listing_results = list(public_listings_for_shop(
        shop=shop, section=selected_section, query=shop_query, sort=shop_sort,
        limit=shop_limit + 1,
    ))
    has_more_listings = len(listing_results) > shop_limit
    listings = listing_results[:shop_limit]
    from apps.marketplace.favorites.models import Favorite, ShopFollow
    from apps.marketplace.shops.permissions import user_is_shop_staff
    is_following = request.user.is_authenticated and ShopFollow.objects.filter(user=request.user, shop=shop).exists()
    is_shop_staff = request.user.is_authenticated and user_is_shop_staff(actor=request.user, shop=shop)
    favorite_listing_ids = set()
    if request.user.is_authenticated:
        favorite_listing_ids = set(Favorite.objects.filter(
            user=request.user, listing_id__in=[listing.id for listing in listings],
        ).values_list('listing_id', flat=True))
    for listing in listings:
        listing.is_favorited_by_viewer = listing.id in favorite_listing_ids

    from django.db.models import Avg, Count, Sum
    from apps.marketplace.orders.models import OrderItem, PaymentStatus
    from apps.marketplace.reviews.models import Review
    shop_review_queryset = Review.objects.filter(shop=shop, is_visible=True).select_related('buyer', 'listing')
    shop_review_summary = shop_review_queryset.aggregate(
        count=Count('id'), overall=Avg('rating'), quality=Avg('quality_rating'),
        shipping=Avg('shipping_rating'), service=Avg('service_rating'),
    )
    rating_counts = {
        row['rating']: row['count']
        for row in shop_review_queryset.values('rating').annotate(count=Count('id'))
    }
    review_total = shop_review_summary['count'] or 0
    review_breakdown = [
        {
            'rating': rating,
            'count': rating_counts.get(rating, 0),
            'percentage': round(rating_counts.get(rating, 0) * 100 / review_total) if review_total else 0,
        }
        for rating in range(5, 0, -1)
    ]
    sales_count = OrderItem.objects.filter(
        shop=shop,
        order__payment_status__in=[PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED],
    ).aggregate(total=Sum('quantity'))['total'] or 0
    shop_banner_url = None
    if shop.banner:
        try:
            if shop.banner.width >= shop.banner.height * 1.8:
                shop_banner_url = shop.banner.url
        except (FileNotFoundError, OSError, ValueError):
            shop_banner_url = None
    return render(
        request,
        'shops/public_shop.html',
        {
            'shop': shop,
            'listings': listings,
            'hero_listings': listings[:3],
            'shop_banner_url': shop_banner_url,
            'listing_count': shop.listings.filter(status=ListingStatus.ACTIVE).count(),
            'has_more_listings': has_more_listings,
            'next_listing_limit': min(shop_limit + 8, 48),
            'sales_count': sales_count,
            'shop_query': shop_query,
            'shop_sort': shop_sort,
            'page_title': shop.name,
            'is_owner': request.user.is_authenticated and shop.owner_id == request.user.id,
            'is_shop_staff': is_shop_staff,
            'is_following': is_following,
            'follower_count': shop.followers.count(),
            'shop_reviews': shop_review_queryset[:3],
            'shop_review_summary': shop_review_summary,
            'review_breakdown': review_breakdown,
            'report_reasons': ReportReason.choices,
            'sections': sections,
            'selected_section': selected_section,
            'shop_share_url': request.build_absolute_uri(reverse('shops:public_shop', kwargs={'slug': shop.slug})),
        },
    )


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

