from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.marketplace.content.models import (
    Collection, CollectionListing, HeroPromoCard, HeroSlide, HomepageSection, PromoBannerAd,
)


class CollectionListingInline(TabularInline):
    model = CollectionListing
    extra = 0
    raw_id_fields = ('listing',)


@admin.register(HomepageSection)
class HomepageSectionAdmin(ModelAdmin):
    list_display = ('title', 'section_type', 'position', 'is_visible', 'starts_at', 'ends_at')
    list_filter = ('section_type', 'is_visible')
    list_editable = ('is_visible', 'position')
    ordering = ('position',)
    actions = ['make_visible', 'make_hidden']

    @admin.action(description='Show selected sections on homepage')
    def make_visible(self, request, queryset):
        queryset.update(is_visible=True)

    @admin.action(description='Hide selected sections from homepage')
    def make_hidden(self, request, queryset):
        queryset.update(is_visible=False)


@admin.register(HeroSlide)
class HeroSlideAdmin(ModelAdmin):
    list_display = ('title', 'status', 'priority', 'starts_at', 'ends_at')
    list_filter = ('status',)
    ordering = ('priority',)


@admin.register(HeroPromoCard)
class HeroPromoCardAdmin(ModelAdmin):
    list_display = ('title', 'badge_text', 'button_label', 'status', 'priority', 'starts_at', 'ends_at')
    list_filter = ('status',)
    ordering = ('priority', '-updated_at')


@admin.register(PromoBannerAd)
class PromoBannerAdAdmin(ModelAdmin):
    list_display = ('title', 'target_url', 'is_active', 'status', 'priority', 'starts_at', 'ends_at')
    list_filter = ('is_active', 'status')
    list_editable = ('is_active', 'status', 'priority')
    search_fields = ('title', 'target_url', 'alt_text')
    ordering = ('priority', '-updated_at')
    actions = ['activate_banners', 'deactivate_banners', 'publish_banners', 'unpublish_banners']

    @admin.action(description='Turn ON (activate) selected banners')
    def activate_banners(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Turn OFF (deactivate) selected banners')
    def deactivate_banners(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description='Publish selected banners')
    def publish_banners(self, request, queryset):
        queryset.update(status='published', is_active=True)

    @admin.action(description='Unpublish selected banners')
    def unpublish_banners(self, request, queryset):
        queryset.update(status='unpublished', is_active=False)


@admin.register(Collection)
class CollectionAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'visibility', 'starts_at', 'ends_at')
    list_filter = ('visibility',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [CollectionListingInline]
    search_fields = ('name', 'slug')

