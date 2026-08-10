from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.search.models import RecentlyViewedListing, SavedSearch


@admin.register(SavedSearch)
class SavedSearchAdmin(ModelAdmin):
    list_display = ('name', 'user', 'alerts_enabled', 'last_checked_at', 'last_notified_at')
    list_filter = ('alerts_enabled',)
    search_fields = ('name', 'query', 'user__email')
    raw_id_fields = ('user',)


@admin.register(RecentlyViewedListing)
class RecentlyViewedListingAdmin(ModelAdmin):
    list_display = ('user', 'listing', 'view_count', 'last_viewed_at')
    search_fields = ('user__email', 'listing__title')
    raw_id_fields = ('user', 'listing')
