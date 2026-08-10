from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.marketplace.cart.models import Cart, CartItem


class CartItemInline(TabularInline):
    model = CartItem
    extra = 0
    raw_id_fields = ('listing', 'variant')


@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'updated_at')
    search_fields = ('user__email', 'session_key')
    inlines = [CartItemInline]
    raw_id_fields = ('user',)


@admin.register(CartItem)
class CartItemAdmin(ModelAdmin):
    list_display = ('cart', 'listing', 'quantity', 'created_at')
    raw_id_fields = ('cart', 'listing', 'variant')
