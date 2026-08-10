from django.contrib import admin
from django.urls import path

from apps.marketplace.cart import views
from apps.marketplace.cart.models import Cart, CartItem

app_name = 'cart'

urlpatterns = [
    path('cart/', views.cart_page, name='page'),
    path('htmx/cart/add/', views.cart_add, name='add'),
    path('htmx/cart/item/<uuid:item_id>/quantity/', views.cart_update_quantity, name='update_quantity'),
    path('cart/item/<uuid:item_id>/remove/', views.cart_remove, name='remove'),
]

