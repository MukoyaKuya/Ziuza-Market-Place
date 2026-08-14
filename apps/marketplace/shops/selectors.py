from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum

from apps.marketplace.shops.models import Shop, ShopMembershipStatus, ShopVerificationStatus

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
