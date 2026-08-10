from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.shipping.models import Shipment, ShipmentEvent, ShippingMethod, ShippingProfile


@admin.register(ShippingMethod)
class ShippingMethodAdmin(ModelAdmin):
    list_display = ('code', 'name', 'base_fee', 'estimated_days_min', 'estimated_days_max', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(Shipment)
class ShipmentAdmin(ModelAdmin):
    list_display = ('seller_order', 'carrier', 'tracking_number', 'status', 'created_at')
    list_filter = ('status', 'carrier')
    search_fields = ('tracking_number', 'carrier')
    raw_id_fields = ('seller_order',)


@admin.register(ShipmentEvent)
class ShipmentEventAdmin(ModelAdmin):
    list_display = ('shipment', 'status', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('shipment',)


@admin.register(ShippingProfile)
class ShippingProfileAdmin(ModelAdmin):
    list_display = ('name', 'shop', 'base_fee', 'free_shipping_threshold', 'allows_local_pickup', 'is_default', 'is_active')
    list_filter = ('offers_delivery', 'allows_local_pickup', 'is_default', 'is_active')
    search_fields = ('name', 'shop__name')
    raw_id_fields = ('shop',)
