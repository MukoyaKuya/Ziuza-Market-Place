from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.marketplace.listings.models import (
    Inventory,
    Listing,
    ListingAttribute,
    ListingImage,
    ListingVariant,
    ListingOption,
    ListingOptionValue,
    PersonalizationField,
    DigitalAsset,
    BulkOperation,
)


class ListingImageInline(TabularInline):
    model = ListingImage
    extra = 0


class ListingVariantInline(TabularInline):
    model = ListingVariant
    extra = 0


class ListingAttributeInline(TabularInline):
    model = ListingAttribute
    extra = 0


class InventoryInline(TabularInline):
    model = Inventory
    extra = 0


@admin.register(Listing)
class ListingAdmin(ModelAdmin):
    list_display = ('title', 'shop', 'category', 'status', 'base_price', 'currency', 'published_at')
    list_filter = ('status', 'currency', 'is_featured')
    search_fields = ('title', 'slug', 'sku', 'shop__name')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ListingImageInline, ListingVariantInline, ListingAttributeInline, InventoryInline]
    raw_id_fields = ('shop', 'category')


@admin.register(Inventory)
class InventoryAdmin(ModelAdmin):
    list_display = ('listing', 'variant', 'quantity_available', 'quantity_reserved', 'updated_at')
    search_fields = ('listing__title',)


@admin.register(ListingOption)
class ListingOptionAdmin(ModelAdmin):
    list_display = ('name', 'listing', 'position')
    search_fields = ('name', 'listing__title')
    raw_id_fields = ('listing',)


@admin.register(ListingOptionValue)
class ListingOptionValueAdmin(ModelAdmin):
    list_display = ('value', 'option', 'position')
    search_fields = ('value', 'option__name', 'option__listing__title')
    raw_id_fields = ('option',)


@admin.register(PersonalizationField)
class PersonalizationFieldAdmin(ModelAdmin):
    list_display = ('label', 'listing', 'field_type', 'is_required', 'position')
    list_filter = ('field_type', 'is_required')
    search_fields = ('label', 'listing__title')
    raw_id_fields = ('listing',)


@admin.register(DigitalAsset)
class DigitalAssetAdmin(ModelAdmin):
    list_display = ('title', 'listing', 'version', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'listing__title', 'version')
    raw_id_fields = ('listing',)


@admin.register(BulkOperation)
class BulkOperationAdmin(ModelAdmin):
    list_display = ('operation', 'shop', 'status', 'dry_run', 'total_rows', 'error_count', 'created_at')
    list_filter = ('operation', 'status', 'dry_run')
    search_fields = ('shop__name', 'actor__email', 'file_name')
    raw_id_fields = ('shop', 'actor')
    readonly_fields = (
        'operation', 'shop', 'actor', 'status', 'file_name', 'dry_run', 'total_rows',
        'created_rows', 'updated_rows', 'error_count', 'summary', 'created_at',
    )

    def has_add_permission(self, request):
        return False
