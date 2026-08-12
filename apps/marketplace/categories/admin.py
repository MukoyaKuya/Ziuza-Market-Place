from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.marketplace.categories.models import Category


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'image_preview', 'parent', 'position', 'is_visible', 'slug')
    list_filter = ('is_visible',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('position', 'name')
    readonly_fields = ('image_preview',)
    fieldsets = (
        ('Category details', {
            'fields': ('name', 'slug', 'parent', 'description', 'icon', 'image', 'image_preview'),
        }),
        ('Display and search', {
            'fields': ('position', 'is_visible', 'seo_title', 'seo_description'),
        }),
    )

    @admin.display(description='Card image')
    def image_preview(self, category):
        if not category or not category.image:
            return 'Default category artwork'
        return format_html(
            '<img src="{}" alt="" style="width: 88px; height: 56px; object-fit: cover; border-radius: 8px;" />',
            category.image.url,
        )
