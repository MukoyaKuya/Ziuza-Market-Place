from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.promotions.models import Promotion, PromotionRedemption


@admin.register(Promotion)
class PromotionAdmin(ModelAdmin):
    list_display = ('code', 'shop', 'discount_type', 'value', 'starts_at', 'ends_at', 'is_active')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code', 'name', 'shop__name')
    raw_id_fields = ('shop',)

@admin.register(PromotionRedemption)
class PromotionRedemptionAdmin(ModelAdmin):
    list_display = ('promotion', 'order', 'user', 'discount_amount', 'status', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('promotion', 'order', 'user')
