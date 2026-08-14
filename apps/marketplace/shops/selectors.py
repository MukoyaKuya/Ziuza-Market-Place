from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, F, Sum

from apps.marketplace.shops.models import Shop, ShopMembership, ShopMembershipStatus, ShopSection, ShopVerificationStatus

User = get_user_model()


def get_shop_for_owner(*, user: User) -> Shop | None:
    return Shop.objects.filter(owner=user).first()


def get_shop_for_user(*, user: User) -> Shop | None:
    owned = get_shop_for_owner(user=user)
    if owned is not None:
        return owned
    return Shop.objects.filter(memberships__user=user, memberships__status=ShopMembershipStatus.ACTIVE).distinct().first()


def get_public_shop_by_slug(*, slug: str) -> Shop:
    """Public shop page — excludes suspended shops."""
    return Shop.objects.select_related('owner').get(
        slug=slug,
        is_active=True,
    )


def shop_is_publicly_listable(shop: Shop) -> bool:
    return shop.is_publicly_visible and shop.verification_status != ShopVerificationStatus.SUSPENDED


def shop_review_context(*, shop: Shop) -> dict:
    """Visible review summary, per-star breakdown, and recent reviews for a public shop page."""
    from apps.marketplace.reviews.models import Review

    queryset = Review.objects.filter(shop=shop, is_visible=True).select_related('buyer', 'listing')
    summary = queryset.aggregate(
        count=Count('id'), overall=Avg('rating'), quality=Avg('quality_rating'),
        shipping=Avg('shipping_rating'), service=Avg('service_rating'),
    )
    review_total = summary['count'] or 0
    rating_counts = {
        row['rating']: row['count']
        for row in queryset.values('rating').annotate(count=Count('id'))
    }
    breakdown = [
        {
            'rating': rating,
            'count': rating_counts.get(rating, 0),
            'percentage': round(rating_counts.get(rating, 0) * 100 / review_total) if review_total else 0,
        }
        for rating in range(5, 0, -1)
    ]
    return {
        'summary': summary,
        'breakdown': breakdown,
        'recent_reviews': queryset[:3],
    }


def shop_sales_count(*, shop: Shop) -> int:
    """Total units sold across paid orders for a shop."""
    from apps.marketplace.orders.models import OrderItem, PaymentStatus

    return (
        OrderItem.objects.filter(
            shop=shop,
            order__payment_status__in=[PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED],
        ).aggregate(total=Sum('quantity'))['total'] or 0
    )


def public_shop_banner_url(*, shop: Shop) -> str | None:
    """Banner URL only when the uploaded image is wide enough for a cover."""
    if not shop.banner:
        return None
    try:
        if shop.banner.width >= shop.banner.height * 1.8:
            return shop.banner.url
    except (FileNotFoundError, OSError, ValueError):
        pass
    return None


def dashboard_listing_stats(*, shop: Shop) -> dict:
    """Active/draft/low-stock/total listing counts for the seller dashboard overview."""
    from apps.marketplace.listings.models import Inventory, Listing, ListingStatus

    status_counts = (
        Listing.objects.filter(shop=shop)
        .values('status')
        .annotate(count=Count('id'))
    )
    by_status = {row['status']: row['count'] for row in status_counts}
    total = sum(by_status.values())
    low_stock = (
        Inventory.objects.filter(
            listing__shop=shop,
            variant__isnull=True,
        )
        .filter(quantity_available__lte=F('low_stock_threshold') + F('quantity_reserved'))
        .values('listing_id')
        .distinct()
        .count()
    )
    return {
        'active_count': by_status.get(ListingStatus.ACTIVE, 0),
        'draft_count': by_status.get(ListingStatus.DRAFT, 0),
        'low_stock_count': low_stock,
        'total_count': total,
    }


def shop_dashboard_reviews(*, shop: Shop):
    """Recent reviews for the seller dashboard reviews page."""
    from apps.marketplace.reviews.models import Review

    return list(
        Review.objects.filter(shop=shop)
        .select_related('buyer', 'listing', 'seller_responded_by')
        .prefetch_related('media')[:50]
    )


def public_shop_sections(*, shop: Shop):
    """Visible sections for the public shop page."""
    return shop.sections.filter(is_visible=True)


def public_shop_section(*, shop: Shop, slug: str):
    """A visible section by slug, or None."""
    return public_shop_sections(shop=shop).filter(slug=slug).first()


def shop_active_listing_count(*, shop: Shop) -> int:
    """Active listing count shown on the public shop page."""
    from apps.marketplace.listings.models import ListingStatus

    return shop.listings.filter(status=ListingStatus.ACTIVE).count()


def shop_follower_count(*, shop: Shop) -> int:
    """Follower count shown on the public shop page."""
    return shop.followers.count()


def storefront_sections(*, shop: Shop):
    """All sections with their listings, for the storefront marketing dashboard."""
    return shop.sections.prefetch_related('listings').all()


def get_shop_section(*, shop: Shop, section_id):
    """A section owned by the shop, or None."""
    return ShopSection.objects.filter(id=section_id, shop=shop).first()


def get_shop_membership(*, shop: Shop, membership_id):
    """A membership of the shop (with user loaded), or None."""
    return ShopMembership.objects.filter(id=membership_id, shop=shop).select_related('user').first()


def shop_verification_applications(*, shop: Shop, limit: int = 10):
    """Recent verification applications for the seller dashboard."""
    return shop.verification_applications.select_related('reviewed_by')[:limit]


def shop_team_memberships(*, shop: Shop):
    """Team memberships with user and inviter loaded."""
    return shop.memberships.select_related('user', 'invited_by')


def shop_pending_team_invitations(*, shop: Shop, limit: int = 20):
    """Team invitations still awaiting acceptance."""
    return (
        shop.team_invitations.filter(accepted_at__isnull=True, revoked_at__isnull=True)
        .select_related('invited_by')[:limit]
    )


def shop_recent_audit_events(*, shop: Shop, limit: int = 50):
    """Recent audit events with actor loaded."""
    return shop.audit_events.select_related('actor')[:limit]
