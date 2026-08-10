from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.utils import timezone

from apps.marketplace.analytics.models import ListingDailyMetric, ShopDailyMetric
from apps.marketplace.favorites.models import Favorite
from apps.marketplace.orders.models import OrderItem, PaymentStatus, SellerOrder
from apps.marketplace.reviews.models import Review
from apps.marketplace.search.models import RecentlyViewedListing
from apps.marketplace.shops.models import Shop

NAIROBI = ZoneInfo('Africa/Nairobi')


def nairobi_today() -> date:
    return timezone.now().astimezone(NAIROBI).date()


def _day_bounds(day: date):
    day_start = timezone.make_aware(datetime.combine(day, time.min), NAIROBI)
    return day_start, day_start + timedelta(days=1)


def rollup_shop_day(*, shop, day: date) -> ShopDailyMetric:
    """Recompute shop + listing daily metrics for one Nairobi calendar day."""
    day_start, day_end = _day_bounds(day)

    paid_orders = SellerOrder.objects.filter(
        shop=shop,
        order__payment_status=PaymentStatus.PAID,
        created_at__gte=day_start,
        created_at__lt=day_end,
    )
    orders_count = paid_orders.count()
    revenue = paid_orders.aggregate(total=Sum('subtotal'))['total'] or Decimal('0.00')

    item_rows = list(
        OrderItem.objects.filter(
            seller_order__shop=shop,
            order__payment_status=PaymentStatus.PAID,
            seller_order__created_at__gte=day_start,
            seller_order__created_at__lt=day_end,
        )
        .values('listing_id', 'title_snapshot')
        .annotate(units_sold=Sum('quantity'), revenue=Sum('line_total'))
    )
    units_sold = sum((row['units_sold'] or 0) for row in item_rows)

    followers = shop.followers.count()
    listing_saves = Favorite.objects.filter(listing__shop=shop).count()
    returning_viewers = (
        RecentlyViewedListing.objects.filter(listing__shop=shop, view_count__gt=1)
        .values('user_id')
        .distinct()
        .count()
    )
    review_count = Review.objects.filter(shop=shop, is_visible=True).count()

    metric, _ = ShopDailyMetric.objects.update_or_create(
        shop=shop,
        date=day,
        defaults={
            'orders': orders_count,
            'units_sold': units_sold,
            'revenue': revenue,
            'followers': followers,
            'listing_saves': listing_saves,
            'returning_viewers': returning_viewers,
            'review_count': review_count,
        },
    )

    seen_listing_uuids = set()
    for row in item_rows:
        listing_uuid = row['listing_id']
        if listing_uuid is None:
            continue
        seen_listing_uuids.add(listing_uuid)
        ListingDailyMetric.objects.update_or_create(
            shop=shop,
            listing_uuid=listing_uuid,
            date=day,
            defaults={
                'listing_id': listing_uuid,
                'title_snapshot': row['title_snapshot'] or 'Listing',
                'units_sold': row['units_sold'] or 0,
                'revenue': row['revenue'] or Decimal('0.00'),
            },
        )

    ListingDailyMetric.objects.filter(shop=shop, date=day).exclude(
        listing_uuid__in=seen_listing_uuids
    ).delete()

    return metric


def rollup_shop_range(*, shop, start: date, end: date) -> int:
    """Roll up inclusive date range. Returns number of days processed."""
    if end < start:
        return 0
    count = 0
    day = start
    while day <= end:
        rollup_shop_day(shop=shop, day=day)
        count += 1
        day += timedelta(days=1)
    return count


def ensure_shop_metrics(*, shop, start: date, end: date) -> int:
    """Fill any missing daily rows in the range (inclusive)."""
    if end < start:
        return 0
    existing = set(
        ShopDailyMetric.objects.filter(shop=shop, date__gte=start, date__lte=end).values_list(
            'date', flat=True
        )
    )
    filled = 0
    day = start
    while day <= end:
        if day not in existing:
            rollup_shop_day(shop=shop, day=day)
            filled += 1
        day += timedelta(days=1)
    return filled


def shops_with_paid_activity(*, since: date | None = None):
    qs = SellerOrder.objects.filter(order__payment_status=PaymentStatus.PAID)
    if since is not None:
        since_start, _ = _day_bounds(since)
        qs = qs.filter(created_at__gte=since_start)
    shop_ids = qs.values_list('shop_id', flat=True).distinct()
    return Shop.objects.filter(id__in=shop_ids)


def rollup_yesterday_for_active_shops() -> int:
    yesterday = nairobi_today() - timedelta(days=1)
    total = 0
    for shop in shops_with_paid_activity(since=yesterday):
        rollup_shop_day(shop=shop, day=yesterday)
        total += 1
    return total
