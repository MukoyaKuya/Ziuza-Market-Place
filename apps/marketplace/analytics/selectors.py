from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate

from apps.marketplace.analytics.models import ListingDailyMetric, ShopDailyMetric
from apps.marketplace.analytics.services import ensure_shop_metrics, nairobi_today
from apps.marketplace.favorites.models import Favorite
from apps.marketplace.orders.models import (
    FulfillmentStatus,
    HelpRequest,
    HelpRequestStatus,
    OrderItem,
    PaymentStatus,
    SellerOrder,
)
from apps.marketplace.reviews.models import Review
from apps.marketplace.search.models import RecentlyViewedListing

ALLOWED_ANALYTICS_DAYS = frozenset({7, 14, 30})


def _window_bounds(*, days: int):
    end = nairobi_today()
    start = end - timedelta(days=days - 1)
    return start, end


def _dense_daily_from_metrics(*, shop, start, end, days: int):
    by_date = {
        row.date: row
        for row in ShopDailyMetric.objects.filter(shop=shop, date__gte=start, date__lte=end)
    }
    series = []
    day = start
    while day <= end:
        row = by_date.get(day)
        series.append(
            {
                'day': day,
                'orders': row.orders if row else 0,
                'revenue': row.revenue if row else Decimal('0.00'),
                'units_sold': row.units_sold if row else 0,
            }
        )
        day += timedelta(days=1)
    # Keep chronological for charts; trim to exact days length if needed
    return series[-days:]


def _dense_daily_live(*, shop, start, end, days: int):
    paid_seller_orders = SellerOrder.objects.filter(
        shop=shop,
        order__payment_status=PaymentStatus.PAID,
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    # TruncDate uses the active timezone (Africa/Nairobi)
    rows = {
        row['day']: row
        for row in (
            paid_seller_orders.annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(orders=Count('id'), revenue=Sum('subtotal'))
        )
        if row['day'] is not None
    }
    series = []
    day = start
    while day <= end:
        row = rows.get(day)
        series.append(
            {
                'day': day,
                'orders': row['orders'] if row else 0,
                'revenue': (row['revenue'] if row and row['revenue'] is not None else Decimal('0.00')),
                'units_sold': 0,
            }
        )
        day += timedelta(days=1)
    return series[-days:]


def _top_listings_from_metrics(*, shop, start, end):
    rows = (
        ListingDailyMetric.objects.filter(shop=shop, date__gte=start, date__lte=end)
        .values('listing_uuid', 'title_snapshot')
        .annotate(units_sold=Sum('units_sold'), revenue=Sum('revenue'))
        .order_by('-units_sold')[:5]
    )
    return [
        {
            'title_snapshot': row['title_snapshot'],
            'listing_id': row['listing_uuid'],
            'units_sold': row['units_sold'] or 0,
            'revenue': row['revenue'] or Decimal('0.00'),
        }
        for row in rows
    ]


def _top_listings_live(*, shop, start, end):
    from datetime import datetime, time
    from zoneinfo import ZoneInfo

    from django.utils import timezone

    nairobi = ZoneInfo('Africa/Nairobi')
    start_dt = timezone.make_aware(datetime.combine(start, time.min), nairobi)
    end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), nairobi)
    top_listings = (
        OrderItem.objects.filter(
            seller_order__shop=shop,
            order__payment_status=PaymentStatus.PAID,
            seller_order__created_at__gte=start_dt,
            seller_order__created_at__lt=end_dt,
        )
        .values('title_snapshot', 'listing_id')
        .annotate(units_sold=Sum('quantity'), revenue=Sum('line_total'))
        .order_by('-units_sold')[:5]
    )
    return list(top_listings)


def shop_analytics_summary(*, shop, days: int = 14):
    if days not in ALLOWED_ANALYTICS_DAYS:
        days = 14
    start, end = _window_bounds(days=days)

    metric_count = ShopDailyMetric.objects.filter(shop=shop, date__gte=start, date__lte=end).count()
    use_metrics = metric_count > 0

    if use_metrics:
        daily = _dense_daily_from_metrics(shop=shop, start=start, end=end, days=days)
        window_agg = ShopDailyMetric.objects.filter(shop=shop, date__gte=start, date__lte=end).aggregate(
            revenue=Sum('revenue'),
            order_count=Sum('orders'),
            units=Sum('units_sold'),
        )
        revenue = window_agg['revenue'] or Decimal('0.00')
        order_count = window_agg['order_count'] or 0
        units = window_agg['units'] or 0
        top_listings = _top_listings_from_metrics(shop=shop, start=start, end=end)
        if not top_listings:
            top_listings = _top_listings_live(shop=shop, start=start, end=end)
    else:
        daily = _dense_daily_live(shop=shop, start=start, end=end, days=days)
        revenue = sum((row['revenue'] or Decimal('0.00')) for row in daily)
        order_count = sum(row['orders'] for row in daily)
        units = (
            OrderItem.objects.filter(
                seller_order__shop=shop,
                order__payment_status=PaymentStatus.PAID,
            )
            .aggregate(total=Sum('quantity'))['total']
            or 0
        )
        # Lifetime units when no metrics — but for window consistency use live window top listings
        top_listings = _top_listings_live(shop=shop, start=start, end=end)
        # Window units from items
        from datetime import datetime, time
        from zoneinfo import ZoneInfo

        from django.utils import timezone

        nairobi = ZoneInfo('Africa/Nairobi')
        start_dt = timezone.make_aware(datetime.combine(start, time.min), nairobi)
        end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), nairobi)
        units = (
            OrderItem.objects.filter(
                seller_order__shop=shop,
                order__payment_status=PaymentStatus.PAID,
                seller_order__created_at__gte=start_dt,
                seller_order__created_at__lt=end_dt,
            ).aggregate(total=Sum('quantity'))['total']
            or 0
        )

    # Lifetime-ish live KPIs (unchanged semantics for overview / protection / audience)
    paid_seller_orders = SellerOrder.objects.filter(
        shop=shop,
        order__payment_status=PaymentStatus.PAID,
    )
    lifetime_revenue = paid_seller_orders.aggregate(total=Sum('subtotal'))['total'] or Decimal('0.00')
    lifetime_order_count = paid_seller_orders.count()
    lifetime_units_sold = (
        OrderItem.objects.filter(
            seller_order__shop=shop,
            order__payment_status=PaymentStatus.PAID,
        ).aggregate(total=Sum('quantity'))['total']
        or 0
    )

    review_stats = Review.objects.filter(shop=shop, is_visible=True).aggregate(
        count=Count('id'),
        avg=Sum('rating'),
    )
    review_count = review_stats['count'] or 0
    avg_rating = None
    if review_count:
        avg_rating = round((review_stats['avg'] or 0) / review_count, 2)
    review_breakdown = Review.objects.filter(shop=shop, is_visible=True).aggregate(
        quality=Sum('quality_rating'),
        shipping=Sum('shipping_rating'),
        service=Sum('service_rating'),
        responses=Count('seller_responded_at'),
    )
    review_quality_average = (
        round((review_breakdown['quality'] or 0) / review_count, 2) if review_count else None
    )
    review_shipping_average = (
        round((review_breakdown['shipping'] or 0) / review_count, 2) if review_count else None
    )
    review_service_average = (
        round((review_breakdown['service'] or 0) / review_count, 2) if review_count else None
    )
    review_response_rate = (
        round((review_breakdown['responses'] or 0) * 100 / review_count) if review_count else None
    )

    pending_fulfillment = (
        SellerOrder.objects.filter(
            shop=shop,
            order__payment_status=PaymentStatus.PAID,
        )
        .exclude(
            fulfillment_status__in=[
                FulfillmentStatus.DELIVERED,
                FulfillmentStatus.CANCELLED,
            ]
        )
        .count()
    )

    recent_orders = list(
        SellerOrder.objects.filter(shop=shop)
        .select_related('order')
        .order_by('-created_at')[:5]
    )
    protection_cases = HelpRequest.objects.filter(seller_order__shop=shop)
    protection_case_count = protection_cases.count()
    active_protection_cases = protection_cases.filter(
        status__in=[
            HelpRequestStatus.OPEN,
            HelpRequestStatus.SELLER_RESPONDED,
            HelpRequestStatus.ESCALATED,
        ]
    ).count()
    escalated_protection_cases = protection_cases.filter(escalated_at__isnull=False).count()
    responded_cases = protection_cases.filter(first_seller_response_at__isnull=False)
    on_time_responses = sum(
        1
        for case in responded_cases.only('first_seller_response_at', 'response_due_at')
        if case.response_due_at and case.first_seller_response_at <= case.response_due_at
    )
    responded_count = responded_cases.count()
    response_rate = round(on_time_responses * 100 / responded_count) if responded_count else None
    case_rate = (
        round(protection_case_count * 100 / lifetime_order_count, 1) if lifetime_order_count else 0
    )
    follower_count = shop.followers.count()
    listing_save_count = Favorite.objects.filter(listing__shop=shop).count()
    returning_viewers = (
        RecentlyViewedListing.objects.filter(listing__shop=shop, view_count__gt=1)
        .values('user_id')
        .distinct()
        .count()
    )

    return {
        'revenue': revenue,
        'order_count': order_count,
        'units_sold': units,
        'lifetime_revenue': lifetime_revenue,
        'lifetime_order_count': lifetime_order_count,
        'lifetime_units_sold': lifetime_units_sold,
        'top_listings': top_listings,
        'daily': daily,
        'daily_chart_max_orders': max((row['orders'] for row in daily), default=0),
        'selected_days': days,
        'range_start': start,
        'range_end': end,
        'review_count': review_count,
        'avg_rating': avg_rating,
        'review_quality_average': review_quality_average,
        'review_shipping_average': review_shipping_average,
        'review_service_average': review_service_average,
        'review_response_rate': review_response_rate,
        'pending_fulfillment': pending_fulfillment,
        'recent_orders': recent_orders,
        'protection_case_count': protection_case_count,
        'active_protection_cases': active_protection_cases,
        'escalated_protection_cases': escalated_protection_cases,
        'on_time_case_response_rate': response_rate,
        'protection_case_rate': case_rate,
        'follower_count': follower_count,
        'listing_save_count': listing_save_count,
        'returning_viewers': returning_viewers,
    }


# Re-export for views that call ensure before summary
__all__ = [
    'ALLOWED_ANALYTICS_DAYS',
    'ensure_shop_metrics',
    'nairobi_today',
    'shop_analytics_summary',
]
