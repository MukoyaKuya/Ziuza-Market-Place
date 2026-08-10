from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.analytics.models import ListingDailyMetric, ShopDailyMetric


@admin.register(ShopDailyMetric)
class ShopDailyMetricAdmin(ModelAdmin):
    list_display = (
        'shop',
        'date',
        'orders',
        'units_sold',
        'revenue',
        'followers',
        'review_count',
    )
    list_filter = ('date',)
    search_fields = ('shop__name',)
    raw_id_fields = ('shop',)
    date_hierarchy = 'date'


@admin.register(ListingDailyMetric)
class ListingDailyMetricAdmin(ModelAdmin):
    list_display = (
        'title_snapshot',
        'shop',
        'date',
        'units_sold',
        'revenue',
        'listing_uuid',
    )
    list_filter = ('date',)
    search_fields = ('title_snapshot', 'shop__name', 'listing_uuid')
    raw_id_fields = ('shop', 'listing')
    date_hierarchy = 'date'
