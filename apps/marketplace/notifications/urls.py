from django.urls import path

from apps.marketplace.notifications import views

app_name = 'notifications'

urlpatterns = [
    path('account/notifications/', views.notification_list, name='list'),
    path('account/notifications/settings/', views.notification_settings, name='settings'),
    path('account/notifications/<uuid:notification_id>/read/', views.mark_read, name='mark_read'),
    path('account/notifications/unread-count/', views.unread_count_partial, name='unread_count'),
]
