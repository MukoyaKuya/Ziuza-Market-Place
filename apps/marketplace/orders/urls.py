from django.urls import path

from apps.marketplace.orders import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/whatsapp/<str:public_number>/', views.whatsapp_checkout, name='whatsapp_checkout'),
    path('account/orders/', views.buyer_orders, name='buyer_list'),
    path('account/orders/<str:public_number>/', views.buyer_order_detail, name='buyer_detail'),
    path('account/orders/<str:public_number>/cancel/', views.buyer_order_cancel, name='buyer_cancel'),
    path('seller/orders/', views.seller_orders, name='seller_list'),
    path('seller/orders/<uuid:seller_order_id>/', views.seller_order_detail, name='seller_detail'),
    path('account/orders/shop/<uuid:seller_order_id>/help/', views.buyer_help_create, name='buyer_help_create'),
    path('account/help/<uuid:case_id>/', views.buyer_help_detail, name='buyer_help_detail'),
    path('account/help/<uuid:case_id>/escalate/', views.buyer_help_escalate, name='buyer_help_escalate'),
    path('seller/help/<uuid:case_id>/respond/', views.seller_help_respond, name='seller_help_respond'),
    path('account/help/<uuid:case_id>/message/', views.protection_case_message, name='case_message'),
    path('account/help/<uuid:case_id>/evidence/', views.protection_case_evidence, name='case_evidence'),
    path('account/help/evidence/<uuid:evidence_id>/download/', views.protection_case_evidence_download, name='case_evidence_download'),
    path('account/downloads/<uuid:grant_id>/<uuid:asset_id>/', views.download_digital_asset, name='download_asset'),
    path('account/orders/<str:public_number>/status-partial/', views.buyer_order_status_partial, name='buyer_status_partial'),
]
