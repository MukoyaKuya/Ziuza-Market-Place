from django.urls import path

from apps.marketplace.content import views

app_name = 'content'

urlpatterns = [
    path('collections/<slug:slug>/', views.collection_detail, name='collection_detail'),
]
