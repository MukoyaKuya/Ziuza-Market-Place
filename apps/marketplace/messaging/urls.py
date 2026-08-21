from django.urls import path

from apps.marketplace.messaging import views

app_name = 'messaging'

urlpatterns = [
    path('account/messages/', views.buyer_inbox, name='buyer_inbox'),
    path('account/messages/<uuid:conversation_id>/', views.conversation_detail, name='detail'),
    path('listing/<uuid:listing_id>/message/', views.start_from_listing, name='start_from_listing'),
    path('seller/messages/', views.seller_inbox, name='seller_inbox'),
    path('listing/<uuid:listing_id>/custom-order/', views.request_custom_order, name='request_custom_order'),
    path('seller/custom-orders/', views.seller_custom_orders, name='seller_custom_orders'),
    path('account/custom-orders/', views.buyer_custom_orders, name='buyer_custom_orders'),
    path('seller/custom-orders/<uuid:request_id>/respond/', views.seller_custom_order_respond, name='seller_custom_order_respond'),
]
