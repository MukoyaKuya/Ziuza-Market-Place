from django.urls import path

from apps.marketplace.listings import views

app_name = 'listings'

urlpatterns = [
    # Seller
    path('seller/listings/', views.seller_listing_list, name='seller_list'),
    path('seller/listings/new/', views.seller_listing_create, name='seller_create'),
    path('seller/listings/<uuid:listing_id>/', views.seller_listing_detail, name='seller_detail'),
    path('seller/listings/<uuid:listing_id>/edit/', views.seller_listing_edit, name='seller_edit'),
    path('seller/listings/<uuid:listing_id>/publish/', views.seller_listing_publish, name='seller_publish'),
    path('seller/listings/<uuid:listing_id>/pause/', views.seller_listing_pause, name='seller_pause'),
    path('seller/listings/<uuid:listing_id>/archive/', views.seller_listing_archive, name='seller_archive'),
    path('seller/listings/<uuid:listing_id>/inventory/', views.seller_listing_inventory, name='seller_set_inventory'),
    path('seller/listings/<uuid:listing_id>/images/', views.seller_listing_add_image, name='seller_add_image'),
    path('seller/listings/<uuid:listing_id>/variants/', views.seller_listing_add_variant, name='seller_add_variant'),
    path('seller/listings/<uuid:listing_id>/attributes/', views.seller_listing_add_attribute, name='seller_add_attribute'),
    path('seller/listings/<uuid:listing_id>/options/', views.seller_listing_add_option, name='seller_add_option'),
    path('seller/listings/<uuid:listing_id>/personalization/', views.seller_listing_add_personalization, name='seller_add_personalization'),
    path('seller/listings/<uuid:listing_id>/digital-assets/', views.seller_listing_add_digital_asset, name='seller_add_digital_asset'),
    path('seller/inventory/', views.seller_inventory_overview, name='seller_inventory'),
    path('seller/bulk/', views.seller_bulk_tools, name='seller_bulk_tools'),
    path('seller/bulk/export/', views.seller_bulk_export, name='seller_bulk_export'),

    # Public
    path('picks/', views.ziuza_picks, name='ziuza_picks'),
    path('zawadi/', views.zawadi_index, name='zawadi_index'),
    path('zawadi/<slug:slug>/', views.zawadi_category_detail, name='zawadi_category_detail'),
    path('listing/<slug:slug>/', views.listing_detail, name='detail'),
    path('listing/<slug:slug>/report/', views.report_listing, name='report'),
    path('categories/', views.category_index, name='category_index'),
    path('categories/<slug:slug>/', views.category_detail, name='category_detail'),
]
