from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.favorites.models import (
    CollectionItem, Favorite, ListingAlert, ListingCollection, ShopFollow,
)


@admin.register(Favorite)
class FavoriteAdmin(ModelAdmin):
    list_display = ('user', 'listing', 'created_at')
    raw_id_fields = ('user', 'listing')


@admin.register(ListingCollection)
class ListingCollectionAdmin(ModelAdmin):
    list_display = ('name', 'user', 'is_public', 'created_at')
    list_filter = ('is_public',)
    search_fields = ('name', 'user__email', 'description')
    raw_id_fields = ('user',)


@admin.register(CollectionItem)
class CollectionItemAdmin(ModelAdmin):
    list_display = ('collection', 'listing', 'added_at')
    search_fields = ('collection__name', 'listing__title', 'collection__user__email')
    raw_id_fields = ('collection', 'listing')


@admin.register(ShopFollow)
class ShopFollowAdmin(ModelAdmin):
    list_display = ('user', 'shop', 'alerts_enabled', 'created_at')
    list_filter = ('alerts_enabled',)
    search_fields = ('user__email', 'shop__name')
    raw_id_fields = ('user', 'shop')


@admin.register(ListingAlert)
class ListingAlertAdmin(ModelAdmin):
    list_display = ('user', 'listing', 'price_change_enabled', 'back_in_stock_enabled', 'last_checked_at')
    list_filter = ('price_change_enabled', 'back_in_stock_enabled')
    search_fields = ('user__email', 'listing__title')
    raw_id_fields = ('user', 'listing')
