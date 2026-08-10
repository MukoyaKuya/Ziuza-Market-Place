from django.contrib import admin
from django.urls import path

from apps.marketplace.shipping import views
from apps.marketplace.shipping.models import Shipment, ShippingMethod

app_name = 'shipping'

urlpatterns = [
    path('seller/shipping/', views.shipping_profiles, name='profiles'),
    path(
        'seller/orders/<uuid:seller_order_id>/fulfillment/',
        views.seller_update_fulfillment,
        name='update_fulfillment',
    ),
]
