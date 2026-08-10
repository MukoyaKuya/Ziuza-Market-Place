from django.urls import path
from apps.marketplace.promotions import views

app_name = 'promotions'
urlpatterns = [
    path('seller/promotions/', views.seller_promotions, name='seller_list'),
    path('seller/promotions/<uuid:promotion_id>/toggle/', views.toggle_promotion, name='toggle'),
]
