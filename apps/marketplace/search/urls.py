from django.urls import path

from apps.marketplace.search import views

app_name = 'search'

urlpatterns = [
    path('search/', views.search_results, name='results'),
    path('search/save/', views.save_current_search, name='save'),
    path('account/saved-searches/', views.saved_searches, name='saved'),
    path('account/saved-searches/<uuid:saved_id>/alerts/', views.toggle_saved_search_alerts, name='toggle_alerts'),
    path('account/saved-searches/<uuid:saved_id>/delete/', views.delete_saved_search, name='delete_saved'),
    path('account/recently-viewed/clear/', views.clear_recently_viewed, name='clear_recent'),
    path('htmx/search/suggestions/', views.search_suggestions, name='suggestions'),
]
