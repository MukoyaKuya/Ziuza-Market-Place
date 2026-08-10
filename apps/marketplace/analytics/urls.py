from django.urls import path

from apps.marketplace.analytics import views

app_name = 'analytics'

urlpatterns = [
    path('seller/analytics/', views.seller_analytics, name='seller'),
]
