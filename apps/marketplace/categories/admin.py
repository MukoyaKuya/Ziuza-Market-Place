from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.categories.models import Category


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'parent', 'position', 'is_visible', 'slug')
    list_filter = ('is_visible',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('position', 'name')

