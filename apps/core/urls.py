from django.urls import path
from .views import HomeView, DesignSystemView

app_name = 'core'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('design-system/', DesignSystemView.as_view(), name='design-system'),
]
