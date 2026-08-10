from django.contrib import admin
from django.urls import path

from apps.marketplace.payments import views
from apps.marketplace.payments.models import Payment

app_name = 'payments'

urlpatterns = [
    path('checkout/pay/<str:public_number>/', views.initiate_payment, name='initiate'),
    path('payments/callback/fake/', views.fake_callback, name='fake_callback'),
    path('payments/callback/mpesa/', views.mpesa_callback, name='mpesa_callback'),
    path('checkout/pay/<str:public_number>/confirm/', views.fake_confirm, name='fake_confirm'),
    path(
        'checkout/pay/<str:public_number>/mpesa-sandbox-confirm/',
        views.mpesa_sandbox_confirm,
        name='mpesa_sandbox_confirm',
    ),
]
