from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.marketplace.content.models import Collection, CollectionListing, HeroPromoCard, HeroSlide, HomepageSection


class CollectionListingInline(TabularInline):
    model = CollectionListing
    extra = 0
    raw_id_fields = ('listing',)


@admin.register(HomepageSection)
class HomepageSectionAdmin(ModelAdmin):
    list_display = ('title', 'section_type', 'position', 'is_visible', 'starts_at', 'ends_at')
    list_filter = ('section_type', 'is_visible')
    ordering = ('position',)


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


@admin.register(Collection)
class CollectionAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'visibility', 'starts_at', 'ends_at')
    list_filter = ('visibility',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [CollectionListingInline]
    search_fields = ('name', 'slug')

