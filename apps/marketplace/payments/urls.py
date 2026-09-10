from django.urls import path

from apps.marketplace.payments import views

app_name = 'payments'

urlpatterns = [
    path('checkout/pay/<str:public_number>/', views.initiate_payment, name='initiate'),
    path(
        'seller/orders/<uuid:seller_order_id>/confirm-payment/',
        views.seller_confirm_whatsapp,
        name='seller_confirm_whatsapp',
    ),
    path('payments/callback/fake/', views.fake_callback, name='fake_callback'),
    path('payments/callback/mpesa/', views.mpesa_callback, name='mpesa_callback'),
    path('checkout/pay/<str:public_number>/confirm/', views.fake_confirm, name='fake_confirm'),
    path(
        'checkout/pay/<str:public_number>/mpesa-sandbox-confirm/',
        views.mpesa_sandbox_confirm,
        name='mpesa_sandbox_confirm',
    ),
]
