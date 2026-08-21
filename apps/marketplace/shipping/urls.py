from django.urls import path

from apps.marketplace.shipping import views

app_name = 'shipping'

urlpatterns = [
    path('seller/shipping/', views.shipping_profiles, name='profiles'),
    path(
        'seller/orders/<uuid:seller_order_id>/fulfillment/',
        views.seller_update_fulfillment,
        name='update_fulfillment',
    ),
]
