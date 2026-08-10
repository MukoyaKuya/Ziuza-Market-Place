from django.urls import path

from apps.marketplace.favorites import views

app_name = 'favorites'

urlpatterns = [
    path('account/favorites/', views.favorites_list, name='list'),
    path('account/collections/create/', views.collection_create, name='collection_create'),
    path('account/collections/<uuid:collection_id>/update/', views.collection_update, name='collection_update'),
    path('account/collections/add/<uuid:listing_id>/', views.collection_add, name='collection_add'),
    path('account/collections/item/<uuid:item_id>/remove/', views.collection_remove, name='collection_remove'),
    path('buyer-collections/<uuid:collection_id>/', views.collection_public, name='collection_public'),
    path('shops/<uuid:shop_id>/follow/', views.shop_follow_toggle, name='shop_follow_toggle'),
    path('account/follows/<uuid:follow_id>/alerts/', views.shop_follow_alerts, name='shop_follow_alerts'),
    path('listings/<uuid:listing_id>/alerts/', views.listing_alert_toggle, name='listing_alert_toggle'),
    path('htmx/favorites/<uuid:listing_id>/toggle/', views.toggle_favorite_htmx, name='toggle'),
]
