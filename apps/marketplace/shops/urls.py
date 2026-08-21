from django.urls import path

from apps.marketplace.shops import views

app_name = 'shops'

urlpatterns = [
    path('local/', views.local_index, name='local'),
    path('locations/sub-counties-options/', views.location_sub_counties_options, name='sub_counties_options'),
    path('locations/wards-options/', views.location_wards_options, name='wards_options'),
    path('sell/', views.sell_entry, name='sell_entry'),
    path('sell/onboarding/', views.shop_onboarding, name='onboarding'),
    path('seller/', views.dashboard_overview, name='dashboard'),
    path('seller/shop/', views.dashboard_shop_settings, name='dashboard_shop'),
    path('seller/local/', views.dashboard_local_settings, name='dashboard_local'),
    path('seller/storefront/', views.storefront_marketing, name='storefront'),
    path('seller/team/', views.team_management, name='team'),
    path('seller/team/accept/<str:token>/', views.accept_team, name='accept_team'),
    path('seller/reviews/', views.dashboard_reviews, name='dashboard_reviews'),
    path('seller/gifts/', views.dashboard_gifts, name='dashboard_gifts'),
    path('seller/verification/', views.verification, name='verification'),
    path('shop/<slug:slug>/', views.public_shop, name='public_shop'),
    path('shop/<slug:slug>/report/', views.report_shop, name='report_shop'),
]
